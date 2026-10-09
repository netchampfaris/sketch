"""Embed uploaded images in importable modules inside the prototype tree."""

import base64
import binascii
import io
import json
import xml.etree.ElementTree as ET

import frappe
from PIL import Image, UnidentifiedImageError

MAX_ASSET_BYTES = 512_000
MIME_FORMATS = {
	"image/png": "PNG",
	"image/jpeg": "JPEG",
	"image/gif": "GIF",
	"image/webp": "WEBP",
	"image/svg+xml": "SVG",
}


def image_module(data_base64: str, mime_type: str) -> str:
	"""Validate an image and export its data URL. No server-side URL fetches."""
	if mime_type not in MIME_FORMATS:
		frappe.throw("mime_type must be image/png, image/jpeg, image/gif, image/webp, or image/svg+xml")
	try:
		raw = base64.b64decode(data_base64, validate=True)
	except (binascii.Error, ValueError):
		frappe.throw("data_base64 must contain valid base64 without a data URL prefix")
	if not raw or len(raw) > MAX_ASSET_BYTES:
		frappe.throw(f"An image must contain between 1 and {MAX_ASSET_BYTES} bytes")

	try:
		if mime_type == "image/svg+xml":
			text = raw.decode("utf-8")
			if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
				raise ValueError("SVG declarations are not supported")
			if ET.fromstring(text).tag not in ("svg", "{http://www.w3.org/2000/svg}svg"):
				raise ValueError("not an SVG")
		else:
			with Image.open(io.BytesIO(raw)) as image:
				if image.format != MIME_FORMATS[mime_type]:
					raise ValueError("image format does not match mime_type")
				image.verify()
	except (ValueError, ET.ParseError, UnidentifiedImageError, OSError, Image.DecompressionBombError):
		frappe.throw("data_base64 must contain a valid image matching mime_type")

	url = f"data:{mime_type};base64,{base64.b64encode(raw).decode('ascii')}"
	return f"export default {json.dumps(url)};\n"
