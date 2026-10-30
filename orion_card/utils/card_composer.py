import frappe
import os
import io
from PIL import Image, ImageDraw, ImageFont
from orion_card.utils.qr_generator import generate_qr


def get_font(size: int, bold: bool = False):
    """Load best available serif font, fall back to default"""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
        "/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def load_card_image(url: str) -> Image.Image:
    """Load card design image from Frappe file URL"""
    if not url:
        frappe.throw("No card design uploaded for this occasion. Please upload a card design image under the Card tab first.")
    if url.startswith("/"):
        site_path = frappe.get_site_path()
        file_path = os.path.join(site_path, "public", url.lstrip("/"))
        if not os.path.exists(file_path):
            file_path = os.path.join(site_path, url.lstrip("/"))
        if not os.path.exists(file_path):
            frappe.throw(f"Card design file not found at: {url}")
        return Image.open(file_path).convert("RGBA")
    else:
        import requests
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content)).convert("RGBA")


def hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def compose_card_image(occasion_doc, name_text: str, type_text: str, code_text: str, guest_code: str = None) -> Image.Image:
    """Compose card with reference layout:
      - Card type:   top-right corner (bold overlay text)
      - QR code:     bottom-left corner (white badge box)
      - Guest name:  bottom-left, to the right of the QR box (bold, caps)
      - Card number: below the name, to the right of the QR box ("NO: <code>")
    """
    card_img = load_card_image(occasion_doc.card_design)
    width, height = card_img.size

    draw = ImageDraw.Draw(card_img)

    type_rgb = hex_to_rgb(occasion_doc.card_type_color or "#FFFFFF")
    no_rgb = hex_to_rgb(occasion_doc.name_color or "#1A1A1A")

    margin = int(width * 0.025)
    qr_box_size = int(width * 0.16)
    pad = int(qr_box_size * 0.08)
    qr_size = qr_box_size - 2 * pad

    # --- Card type: top-right corner ---
    raw_type = type_text.strip()
    display_type = raw_type if len(raw_type) <= 3 else raw_type.title()
    type_font_size = max(int(width * 0.018), 9)
    type_font = get_font(type_font_size, bold=False)
    type_bbox = draw.textbbox((0, 0), display_type, font=type_font)
    type_w = type_bbox[2] - type_bbox[0]
    type_h = type_bbox[3] - type_bbox[1]
    type_x = width - margin - type_w
    type_y = margin
    # drop shadow for legibility on any background
    draw.text((type_x - type_bbox[0] + 1, type_y - type_bbox[1] + 1), display_type, font=type_font, fill=(0, 0, 0, 160))
    draw.text((type_x - type_bbox[0], type_y - type_bbox[1]), display_type, font=type_font, fill=type_rgb)

    # --- QR code: bottom-left, white badge box ---
    box_x1 = margin
    box_y1 = height - margin - qr_box_size
    box_x2 = box_x1 + qr_box_size
    box_y2 = height - margin

    draw.rounded_rectangle(
        [box_x1, box_y1, box_x2, box_y2],
        radius=max(int(qr_box_size * 0.035), 4),
        fill=(255, 255, 255, 255),
        outline=(220, 220, 220, 255),
        width=1,
    )

    qr_x = box_x1 + pad
    qr_y = box_y1 + pad

    qr_buffer = generate_qr(guest_code or code_text, occasion_doc.name)
    qr_img = Image.open(qr_buffer).convert("RGBA")
    qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
    card_img.paste(qr_img, (qr_x, qr_y), qr_img)

    # --- Guest name + card number: to the right of the QR box, bottom-aligned ---
    side_x = box_x2 + int(margin * 0.5)
    side_max_w = width - side_x - margin

    display_code = guest_code or code_text.replace("Code: ", "")
    no_label = f"NO: {display_code}"
    no_font_size = max(int(width * 0.014), 8)
    no_font = get_font(no_font_size, bold=False)
    no_bbox = draw.textbbox((0, 0), no_label, font=no_font)
    no_h = no_bbox[3] - no_bbox[1]

    name_font_size = max(int(width * 0.016), 9)
    name_font = get_font(name_font_size, bold=False)
    display_name = name_text.upper()
    # shrink until the name fits in the available side width
    while name_font_size > 7:
        name_font = get_font(name_font_size, bold=False)
        nb = draw.textbbox((0, 0), display_name, font=name_font)
        if (nb[2] - nb[0]) <= side_max_w:
            break
        name_font_size -= 1
    name_bbox = draw.textbbox((0, 0), display_name, font=name_font)
    name_h = name_bbox[3] - name_bbox[1]

    gap = int(margin * 0.4)
    block_h = name_h + gap + no_h
    # align the block to the bottom of the QR box
    block_top = box_y2 - block_h

    # guest name
    name_y = block_top
    draw.text((side_x - name_bbox[0], name_y - name_bbox[1]), display_name, font=name_font, fill=no_rgb)

    # card number
    no_y = block_top + name_h + gap
    draw.text((side_x - no_bbox[0], no_y - no_bbox[1]), no_label, font=no_font, fill=no_rgb)

    return card_img


def compose_card(occasion_doc, guest_row):
    card_img = compose_card_image(
        occasion_doc, guest_row.contributor_name, guest_row.card_type,
        f"Code: {guest_row.guest_code}", guest_code=guest_row.guest_code
    )

    # Save final card as JPEG
    output_buffer = io.BytesIO()
    card_img.convert("RGB").save(output_buffer, format="JPEG", quality=93)
    output_buffer.seek(0)

    filename = f"occasion_card_{guest_row.guest_code}.jpg"

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": filename,
        "content": output_buffer.read(),
        "is_private": 0,
        "folder": "Home/Attachments",
    })
    file_doc.save(ignore_permissions=True)

    guest_row.card_image = file_doc.file_url

    base = frappe.utils.get_url().rstrip("/")
    guest_row.download_url = f"{base}/invitee/download/occasion-card/{guest_row.guest_code}"

    frappe.db.commit()
    return file_doc.file_url


def issue_single_card(occasion, contributor):
    """Compose one contributor's card, showing the capacity error as a normal message."""
    from orion_card.orioncard.doctype.occasion.occasion import CardLimitError

    try:
        occasion.issue_card(contributor)
    except CardLimitError as e:
        frappe.throw(f"{contributor.contributor_name}: {e}")


@frappe.whitelist()
def compose_single_guest(occasion_name: str, guest_row_name: str):
    """Whitelisted: compose card for a single contributor by its (unique) child row name"""
    occasion = frappe.get_doc("Occasion", occasion_name)
    occasion.check_permission("write")
    occasion.assert_can_send()
    for contributor in occasion.contributors:
        if contributor.name == guest_row_name:
            issue_single_card(occasion, contributor)
            occasion.save()
            return {"success": True, "card_image": contributor.card_image}
    frappe.throw(f"Contributor row '{guest_row_name}' not found in occasion '{occasion_name}'")


@frappe.whitelist()
def generate_preview(occasion_name: str):
    """Whitelisted: (re)generate the styled sample preview shown as Card Design Preview.

    Uses placeholder guest text so it can run any time — even before any real
    guests exist.
    """
    occasion = frappe.get_doc("Occasion", occasion_name)
    occasion.check_permission("write")
    if not occasion.card_design:
        frappe.throw("Please upload a Card Design image first.")

    card_img = compose_card_image(
        occasion, "Jina la Mgeni", "SINGLE", "Code: 000000", guest_code="000000"
    )

    output_buffer = io.BytesIO()
    card_img.convert("RGB").save(output_buffer, format="JPEG", quality=90)
    output_buffer.seek(0)

    # Clean up the previous preview file so these don't pile up
    if occasion.card_preview_image:
        old_file = frappe.db.get_value("File", {"file_url": occasion.card_preview_image}, "name")
        if old_file:
            frappe.delete_doc("File", old_file, ignore_permissions=True, force=True)

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": f"card_preview_{occasion.name}.jpg",
        "content": output_buffer.read(),
        "is_private": 0,
        "folder": "Home/Attachments",
    })
    file_doc.save(ignore_permissions=True)

    frappe.db.set_value("Occasion", occasion.name, "card_preview_image", file_doc.file_url)
    frappe.db.commit()
    return file_doc.file_url
