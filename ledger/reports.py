"""계정과목 마스터와 균형 분개를 사용하는 장부 기준 재무제표."""
from collections import defaultdict
from decimal import Decimal
from .models import Account, Voucher

ZERO = Decimal(0)
PL_CATEGORIES = ('매출액', '매출원가', '판매비와관리비', '영업외수익', '영업외비용', '법인세비용')


def account_group(account):
    if account.element in ('자산', '부채', '자본'):
        return account.element
    if account.category in PL_CATEGORIES:
        return account.category
    return None


def voucher_postings(voucher, accounts):
    """재무제표와 원장에서 공통으로 사용할 검증된 분개를 반환한다."""
    reason = None
    postings = []
    if voucher.is_journal:
        lines = sorted(voucher.journal_lines.all(), key=lambda line: (line.row, line.side == 'credit'))
        debits = sum((line.amount for line in lines if line.side == 'debit'), ZERO)
        credits = sum((line.amount for line in lines if line.side == 'credit'), ZERO)
        if not debits or debits != credits or debits != voucher.amount:
            reason = '차변·대변 분개가 없거나 합계가 일치하지 않습니다.'
        for line in lines:
            opposite = list(dict.fromkeys(str(other.account) for other in lines if other.side != line.side))
            postings.append({'account_id': line.account_id, 'net': line.amount if line.side == 'debit' else -line.amount,
                             'memo': line.memo or voucher.memo, 'row': line.row, 'opposite': ', '.join(opposite)})
    elif not voucher.account_master_id or not voucher.settlement_account_id:
        reason = '계정과목 또는 상대계정 확인이 필요합니다.'
    elif voucher.kind in (Voucher.Kind.INCOME, Voucher.Kind.EXPENSE):
        primary = -voucher.amount if voucher.kind == Voucher.Kind.INCOME else voucher.amount
        postings = [
            {'account_id': voucher.account_master_id, 'net': primary, 'memo': voucher.memo, 'row': None, 'opposite': str(voucher.settlement_account)},
            {'account_id': voucher.settlement_account_id, 'net': -primary, 'memo': voucher.memo, 'row': None, 'opposite': str(voucher.account_master)},
        ]
    else:
        reason = '전표 구분을 확인하세요.'
    if any(p['account_id'] not in accounts or account_group(accounts[p['account_id']]) is None for p in postings):
        reason = '재무제표 분류를 확인할 수 없는 계정과목입니다.'
    return postings, reason


def collect_balances(vouchers):
    """단식전표는 확인된 상대계정으로만 양변을 구성하며 원전표는 변경하지 않는다."""
    accounts = {a.pk: a for a in Account.objects.all()}
    balances = defaultdict(lambda: ZERO)
    excluded = []
    included_count = 0
    for voucher in vouchers.select_related('account_master', 'settlement_account').prefetch_related('journal_lines__account'):
        postings, reason = voucher_postings(voucher, accounts)
        if reason:
            excluded.append({'voucher': voucher, 'reason': reason})
            continue
        for posting in postings:
            balances[posting['account_id']] += posting['net']
        included_count += 1
    return accounts, balances, excluded, included_count


def balance_side(net):
    return '차변' if net > 0 else '대변' if net < 0 else '—'


def account_ledger(account, start, end):
    accounts = {a.pk: a for a in Account.objects.all()}
    opening = debit = credit = ZERO
    rows, excluded = [], []
    included = set()
    vouchers = Voucher.objects.filter(date__lte=end).select_related('account_master', 'settlement_account').prefetch_related('journal_lines__account').order_by('date', 'pk')
    for voucher in vouchers:
        postings, reason = voucher_postings(voucher, accounts)
        if reason:
            # 분개 정보가 부족하면 선택 계정의 거래인지도 확정할 수 없다.
            excluded.append({'voucher': voucher, 'reason': reason})
            continue
        for posting in postings:
            if posting['account_id'] != account.pk:
                continue
            net = posting['net']
            if voucher.date < start:
                opening += net
                continue
            debit += max(net, ZERO)
            credit += max(-net, ZERO)
            running = opening + debit - credit
            rows.append({'voucher': voucher, 'memo': posting['memo'], 'row': posting['row'],
                         'opposite': posting['opposite'], 'debit': max(net, ZERO), 'credit': max(-net, ZERO),
                         'balance': running, 'balance_amount': abs(running), 'balance_side': balance_side(running)})
            included.add(voucher.pk)
    closing = opening + debit - credit
    return {'account': account, 'rows': rows, 'opening': opening, 'opening_amount': abs(opening),
            'opening_side': balance_side(opening), 'debit': debit, 'credit': credit,
            'closing': closing, 'closing_amount': abs(closing), 'closing_side': balance_side(closing),
            'excluded': excluded, 'included_count': len(included)}


def build_income(accounts, balances):
    sections = []
    totals = {}
    for category in PL_CATEGORIES:
        rows = []
        for code, account in accounts.items():
            if account_group(account) != category:
                continue
            # 수익은 대변 잔액, 비용은 차변 잔액. 차감계정은 음수로 표시한다.
            amount = balances.get(code, ZERO) * (-1 if category in ('매출액', '영업외수익') else 1)
            if amount:
                rows.append({'account': account, 'amount': amount})
        totals[category] = sum((row['amount'] for row in rows), ZERO)
        sections.append({'name': category, 'rows': rows, 'total': totals[category]})
    gross = totals['매출액'] - totals['매출원가']
    operating = gross - totals['판매비와관리비']
    pretax = operating + totals['영업외수익'] - totals['영업외비용']
    return {'sections': sections, 'gross_profit': gross, 'operating_profit': operating,
            'pretax_profit': pretax, 'net_profit': pretax - totals['법인세비용']}


def income_statement(start, end):
    vouchers = Voucher.objects.filter(date__gte=start, date__lte=end, is_closing=False)
    accounts, balances, excluded, included = collect_balances(vouchers)
    result = build_income(accounts, balances)
    result.update(excluded=excluded, included_count=included,
                  closing_count=Voucher.objects.filter(date__gte=start, date__lte=end, is_closing=True).count())
    return result


def balance_sheet(as_of):
    accounts, balances, excluded, included = collect_balances(Voucher.objects.filter(date__lte=as_of))
    sections = []
    totals = {}
    for element in ('자산', '부채', '자본'):
        groups = {}
        for code, account in accounts.items():
            if account_group(account) != element:
                continue
            amount = balances.get(code, ZERO) * (1 if element == '자산' else -1)
            if not amount:
                continue
            key = ' / '.join(filter(None, (account.section, account.category)))
            group = groups.setdefault(key, {'name': key, 'rows': [], 'total': ZERO})
            group['rows'].append({'account': account, 'amount': amount})
            group['total'] += amount
        totals[element] = sum((group['total'] for group in groups.values()), ZERO)
        sections.append({'name': element, 'groups': list(groups.values()), 'total': totals[element]})
    unclosed_profit = build_income(accounts, balances)['net_profit']
    equity = totals['자본'] + unclosed_profit
    sections[-1]['total'] = equity
    return {'sections': sections, 'assets': totals['자산'], 'liabilities': totals['부채'],
            'equity': equity, 'unclosed_profit': unclosed_profit,
            'liabilities_equity': totals['부채'] + equity,
            'difference': totals['자산'] - totals['부채'] - equity,
            'excluded': excluded, 'included_count': included}
