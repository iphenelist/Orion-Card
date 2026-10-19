import frappe
import qrcode
from io import BytesIO


def generate_qr(guest_code: str, occasion_name: str) -> BytesIO:
    """
    Generate a QR code image for a guest.
    Encodes the gate check-in URL so scanning opens the validation page directly.
    """
    base_url = frappe.utils.get_url().rstrip("/")

    qr_data = (
        f"{base_url}/gate-checkin"
        f"?code={guest_code}"
        f"&occasion={frappe.utils.quote(occasion_name)}"
    )

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
