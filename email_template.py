"""HTML email for contact-form submissions.

Table-based layout with inline styles, because email clients (Outlook, Gmail) ignore
<style> blocks, flexbox and most modern CSS. Every submitted value is HTML-escaped.
"""
from html import escape
from urllib.parse import quote

# Brand palette (from index.html)
NAVY = "#1E2A36"
INK = "#121A23"
GOLD = "#C7A77B"
GOLD_2 = "#E2CBA5"
PAPER = "#F6F4EF"
PAPER_2 = "#EDE9E1"
TEXT = "#1B232C"
MUTED = "#5F6A76"
LINE = "#E3DED4"

FONT = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
HEADING = "Georgia,'Times New Roman',serif"

BADGES = {
    # category: (label, background, text colour)
    "lead": ("New lead", "#E4F1E8", "#1F6B3A"),
    "solicitation": ("Solicitation", "#FBF0DC", "#8A5A12"),
    "spam": ("Likely spam", "#F8E3E1", "#9B2C22"),
}


def _e(value, fallback="&mdash;"):
    return escape(value) if value else fallback


def _row(label, value_html):
    return f"""
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid {LINE};width:96px;vertical-align:top;
                       font:600 11px/18px {FONT};letter-spacing:.08em;text-transform:uppercase;color:{MUTED};">{label}</td>
            <td style="padding:10px 0;border-bottom:1px solid {LINE};vertical-align:top;
                       font:15px/22px {FONT};color:{TEXT};">{value_html}</td>
          </tr>"""


def html_for(data, subject, timestamp, category, reason, ip):
    label, badge_bg, badge_fg = BADGES.get(category, BADGES["lead"])
    name = _e(data["name"])
    email = escape(data["email"])
    phone = data["phone"]

    email_html = f'<a href="mailto:{escape(quote(data["email"], safe="@.+-_"))}" style="color:{TEXT};text-decoration:underline;">{email}</a>'
    phone_html = (
        f'<a href="tel:{escape(quote(phone, safe="+"))}" style="color:{TEXT};text-decoration:none;">{escape(phone)}</a>'
        if phone else "&mdash;"
    )
    message_html = escape(data["message"]).replace("\r\n", "\n").replace("\n", "<br>")
    reply_href = "mailto:" + escape(quote(data["email"], safe="@.+-_")) + "?subject=" + escape(quote("Re: Your inquiry to Software Matters"))
    preheader = escape(data["message"][:120].replace("\n", " "))

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
<title>{escape(subject)}</title>
</head>
<body style="margin:0;padding:0;background:{PAPER_2};">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{PAPER_2};">{preheader}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{PAPER_2};">
    <tr><td align="center" style="padding:28px 12px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#FFFFFF;border-radius:10px;overflow:hidden;border:1px solid {LINE};">

        <!-- Header -->
        <tr><td style="background:{NAVY};padding:22px 28px;border-bottom:3px solid {GOLD};">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
            <td style="font:600 13px/18px {FONT};letter-spacing:.16em;text-transform:uppercase;color:{GOLD_2};">Software Matters</td>
            <td align="right" style="font:12px/18px {FONT};color:#9EA9B5;">Website inquiry</td>
          </tr></table>
        </td></tr>

        <!-- Title -->
        <tr><td style="padding:28px 28px 6px;">
          <span style="display:inline-block;padding:4px 10px;border-radius:999px;background:{badge_bg};color:{badge_fg};
                       font:700 11px/16px {FONT};letter-spacing:.08em;text-transform:uppercase;">{label}</span>
          <h1 style="margin:14px 0 4px;font:400 26px/32px {HEADING};color:{INK};">{name}</h1>
          <p style="margin:0;font:15px/22px {FONT};color:{MUTED};">{_e(data["company"], "No company given")}</p>
        </td></tr>

        <!-- Message -->
        <tr><td style="padding:20px 28px 4px;">
          <div style="font:600 11px/18px {FONT};letter-spacing:.08em;text-transform:uppercase;color:{MUTED};margin-bottom:8px;">Message</div>
          <div style="background:{PAPER};border-left:3px solid {GOLD};border-radius:4px;padding:16px 18px;
                      font:16px/25px {FONT};color:{TEXT};word-wrap:break-word;">{message_html}</div>
        </td></tr>

        <!-- Contact details -->
        <tr><td style="padding:20px 28px 0;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{_row("Email", email_html)}{_row("Phone", phone_html)}
          </table>
        </td></tr>

        <!-- Reply button -->
        <tr><td style="padding:24px 28px 8px;">
          <table role="presentation" cellpadding="0" cellspacing="0"><tr>
            <td style="background:{NAVY};border-radius:6px;">
              <a href="{reply_href}" style="display:inline-block;padding:12px 22px;font:600 14px/20px {FONT};color:#FFFFFF;text-decoration:none;">Reply to {name} &rarr;</a>
            </td>
          </tr></table>
        </td></tr>

        <!-- Classification -->
        <tr><td style="padding:16px 28px 26px;">
          <p style="margin:0;font:13px/20px {FONT};color:{MUTED};"><strong style="color:{TEXT};">Why {label.lower()}:</strong> {_e(reason)}</p>
        </td></tr>

        <!-- Footer -->
        <tr><td style="background:{PAPER};border-top:1px solid {LINE};padding:14px 28px;
                       font:12px/18px {FONT};color:{MUTED};">
          {_e(timestamp)} &nbsp;&middot;&nbsp; {_e(data["source"])} &nbsp;&middot;&nbsp; IP {_e(ip)}
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""
