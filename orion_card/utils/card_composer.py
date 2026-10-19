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
    """Build the composited card image: a bottom-right white badge box with
    the QR code on top, guest name (bold, caps, wraps onto up to 3 lines for
    long names) and card type (smaller, muted) stacked below it.

    Used both for real guest cards and for the sample preview (with
    placeholder text).
    """
    card_img = load_card_image(occasion_doc.card_design)
    width, height = card_img.size

    draw = ImageDraw.Draw(card_img)

    name_rgb = hex_to_rgb(occasion_doc.name_color or "#1A1A1A")
    type_rgb = hex_to_rgb(occasion_doc.card_type_color or "#777777")

    margin = int(width * 0.025)
    box_width = int(width * 0.16)
    pad = int(box_width * 0.09)
    gap = int(box_width * 0.05)

    qr_size = box_width - 2 * pad
    inner_width = box_width - 2 * pad
    display_name = name_text.upper()
    raw_type = type_text.strip()
    display_type = raw_type if len(raw_type) <= 3 else raw_type.title()

    def wrap_lines(text, font, max_width):
        words = text.split()
        lines, current = [], ""
        for word in words:
            trial = f"{current} {word}".strip()
            if draw.textbbox((0, 0), trial, font=font)[2] <= max_width or not current:
                current = trial
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def truncate_to_fit(text, font, max_width):
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return text
        while text and draw.textbbox((0, 0), text + "…", font=font)[2] > max_width:
            text = text[:-1]
        return (text + "…") if text else text

    # Wrap long names onto up to 3 lines; only shrink the font if a
    # single word still doesn't fit the box width even wrapped.
    name_font_size = max(int(box_width * 0.115), 10)
    while True:
        name_font = get_font(name_font_size, bold=True)
        name_lines = wrap_lines(display_name, name_font, inner_width)
        widest = max(draw.textbbox((0, 0), line, font=name_font)[2] for line in name_lines)
        if (widest <= inner_width and len(name_lines) <= 3) or name_font_size <= 8:
            break
        name_font_size -= 1

    # Last-resort safety net: a single word with no spaces (e.g. a name
    # typed without one) can still overflow the box even at the floor font
    # size — truncate it instead of letting it spill past the badge edge.
    name_lines = [truncate_to_fit(line, name_font, inner_width) for line in name_lines[:3]]

    line_height = int(name_font_size * 1.25)
    name_block_height = line_height * len(name_lines)

    type_font = get_font(max(int(box_width * 0.085), 8), bold=False)
    type_bbox = draw.textbbox((0, 0), display_type, font=type_font)
    type_w, type_h = type_bbox[2] - type_bbox[0], type_bbox[3] - type_bbox[1]

    box_height = pad + qr_size + gap + name_block_height + int(gap * 0.5) + type_h + pad

    box_x2, box_y2 = width - margin, height - margin
    box_x1, box_y1 = box_x2 - box_width, box_y2 - box_height

    draw.rounded_rectangle(
        [box_x1, box_y1, box_x2, box_y2],
        radius=max(int(box_width * 0.035), 4),
        fill=(255, 255, 255, 255),
        outline=(220, 220, 220, 255),
        width=1,
    )

    qr_x = box_x1 + (box_width - qr_size) // 2
    qr_y = box_y1 + pad

    name_y = qr_y + qr_size + gap
    for line in name_lines:
        line_bbox = draw.textbbox((0, 0), line, font=name_font)
        line_w = line_bbox[2] - line_bbox[0]
        line_x = box_x1 + (box_width - line_w) // 2
        draw.text((line_x - line_bbox[0], name_y - line_bbox[1]), line, font=name_font, fill=name_rgb)
        name_y += line_height

    type_x = box_x1 + (box_width - type_w) // 2
    type_y = name_y + int(gap * 0.5)
    draw.text((type_x - type_bbox[0], type_y - type_bbox[1]), display_type, font=type_font, fill=type_rgb)

    qr_buffer = generate_qr(guest_code or code_text, occasion_doc.name)
    qr_img = Image.open(qr_buffer).convert("RGBA")
    qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
    card_img.paste(qr_img, (qr_x, qr_y), qr_img)

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
