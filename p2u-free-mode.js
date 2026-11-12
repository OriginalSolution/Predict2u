/* Predict2U site mode — the ONE switch for paid codes.
   true  = free codes: every booking code and pick list shows to every visitor, no unlock boxes,
           and the engine stops flagging / sealing codes over 25 odds.
   false = paid codes: the p2u-paywall (Paystack via p2u-relay) and engine sealing come back on.
   The engine reads this same line (engine/premium.py free_mode()). Keep the format: `P2U_FREE_CODES = true;` */
window.P2U_FREE_CODES = true;
