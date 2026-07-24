# ============================================================
# ClipDrop - donate.py
# ============================================================
# Single source of truth for the donation link, plus the one helper
# used to open it.
#
# Two places use this:
#   * the "🎁 Support ClipDrop" button in Settings -> About
#   * the "🎁 Support" link in the main popup's footer strip
#
# To change where the button sends users, edit DONATE_URL only —
# nothing else references the address.
# ============================================================

import webbrowser

# Paystack payment page (Support ClipDrop)
DONATE_URL = "https://paystack.shop/pay/qh7vjjsstc"


def open_donation_page():
    """Open the donation page in the user's default browser.

    Returns None ON PURPOSE. This is invoked from a Qt ``mousePressEvent``
    override, whose C++ signature returns void, so sip requires the Python
    handler to return None. ``webbrowser.open()`` returns a bool, and letting
    that bool escape crashes the app with
    ``TypeError: invalid argument to sipBadCatcherResult()``. Swallowing the
    result (and any error) here keeps every caller safe.
    """
    try:
        webbrowser.open(DONATE_URL)
    except Exception:
        pass
