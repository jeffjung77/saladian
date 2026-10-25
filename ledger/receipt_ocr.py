from io import BytesIO
from PIL import Image, ImageOps
from google.cloud import vision


class ReceiptOCRError(Exception):
    pass


def recognize_receipt(photo, on_request=None):
    # Normalize orientation and bound image size before sending to Google.
    with photo.open('rb') as source, Image.open(source) as original:
        image = ImageOps.exif_transpose(original).convert('RGB')
        image.thumbnail((2400, 2400))
        content = BytesIO()
        image.save(content, format='JPEG', quality=90)
    client = vision.ImageAnnotatorClient(transport='rest')
    try:
        if on_request:
            on_request()
        response = client.document_text_detection(
            image=vision.Image(content=content.getvalue()),
            image_context=vision.ImageContext(language_hints=['ko', 'en']),
            timeout=25, retry=None)
        if response.error.message:
            raise ReceiptOCRError('사진 인식에 실패했습니다. 사진을 확인하고 다시 분석하세요.')
        text = response.full_text_annotation.text.strip()
        if not text:
            raise ReceiptOCRError('글자를 찾지 못했습니다. 영수증을 선명하게 다시 촬영해 주세요.')
        return text
    finally:
        client.transport.close()
