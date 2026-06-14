"""
Cloots AI Customer Support Assistant — simple, rule-based.

No external API keys required. Matches the customer's question against a
keyword knowledge base tailored to Cloots (orders, shipping, returns,
payments, price ranges, how to order, account help).

If you later want to plug in a real LLM, replace `answer_question()` with
an API call — the view contract stays the same.
"""

import json
import re

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


# ---------------------------------------------------------------------------
# Knowledge base — edit freely to match your store's real policies / prices.
# Each entry: keywords -> answer. First match wins (checked top to bottom).
# ---------------------------------------------------------------------------
KB = [
    {
        "keywords": ["how to order", "place order", "buy", "purchase", "checkout steps", "how do i order"],
        "answer": (
            "Ordering on Cloots is easy:\n"
            "1. Browse or search for the product you like.\n"
            "2. Click the product, choose size/color, and tap **Add to Cart**.\n"
            "3. Open your cart and click **Proceed to Checkout**.\n"
            "4. Log in (or sign up), enter your shipping address, choose a payment method, and confirm.\n"
            "You'll get an order confirmation email right after payment."
        ),
    },
    {
        "keywords": ["payment method", "payment methods", "how to pay", "pay", "payments"],
        "answer": (
            "Cloots accepts:\n"
            "• Credit / Debit Cards (Visa, MasterCard, American Express)\n"
            "• UPI and Net Banking\n"
            "• PayPal\n"
            "• Cash on Delivery (COD) — available on selected orders"
        ),
    },
    {
        "keywords": ["cod", "cash on delivery"],
        "answer": "Yes, Cash on Delivery is available on most orders. You can choose COD at checkout if it's supported for your address.",
    },
    {
        "keywords": ["shipping", "delivery time", "deliver", "how long", "when will"],
        "answer": (
            "Standard delivery takes **3–7 business days**. Express delivery (1–3 days) is available in select cities. "
            "You'll get a tracking link by email once your order ships."
        ),
    },
    {
        "keywords": ["shipping cost", "delivery charge", "shipping fee", "shipping charges"],
        "answer": "Shipping is **free on orders above ₹999**. Below that, a flat ₹49 delivery fee applies.",
    },
    {
        "keywords": ["return", "refund", "exchange", "send back"],
        "answer": (
            "You can return or exchange any item within **7 days of delivery**, as long as it's unused and has the original tags. "
            "Go to **My Orders → Order Detail → Request Return**. Refunds are processed to your original payment method within 5–7 business days."
        ),
    },
    {
        "keywords": ["track", "tracking", "where is my order", "order status"],
        "answer": "Open **My Account → My Orders** to see real-time status and the tracking link for every order.",
    },
    {
        "keywords": ["cancel"],
        "answer": "You can cancel an order from **My Orders** as long as it hasn't been shipped yet. Once shipped, please use the return option after delivery.",
    },

    # --- Pricing ---
    {
        "keywords": ["price of shirt", "shirt price", "shirts cost", "shirts range", "price range of shirt"],
        "answer": "Shirts on Cloots typically range from **₹499 to ₹1,799**, depending on brand and fabric.",
    },
    {
        "keywords": ["tshirt", "t-shirt", "t shirt"],
        "answer": "T-shirts on Cloots range from **₹299 to ₹1,199**.",
    },
    {
        "keywords": ["jeans", "denim"],
        "answer": "Jeans on Cloots range from **₹899 to ₹2,499**.",
    },
    {
        "keywords": ["shoe", "shoes", "sneaker", "footwear"],
        "answer": "Shoes on Cloots range from **₹999 to ₹4,999**, including sneakers and sports footwear.",
    },
    {
        "keywords": ["jacket", "jackets"],
        "answer": "Jackets on Cloots range from **₹1,499 to ₹4,999**.",
    },
    {
        "keywords": ["price", "cost", "how much"],
        "answer": (
            "Here's a quick price guide on Cloots:\n"
            "• T-shirts: ₹299 – ₹1,199\n"
            "• Shirts: ₹499 – ₹1,799\n"
            "• Jeans: ₹899 – ₹2,499\n"
            "• Jackets: ₹1,499 – ₹4,999\n"
            "• Shoes: ₹999 – ₹4,999\n"
            "Open the product page for the exact price."
        ),
    },

    # --- Account ---
    {
        "keywords": ["sign up", "register", "create account"],
        "answer": "Click **Register** at the top right, enter your name, email and password, and verify your email — that's it!",
    },
    {
        "keywords": ["login", "log in", "sign in"],
        "answer": "Click **Login** at the top right and enter your registered email and password.",
    },
    {
        "keywords": ["forgot password", "reset password", "can't login", "cant login"],
        "answer": "On the login page, click **Forgot Password?**, enter your email, and follow the reset link we send you.",
    },
    {
        "keywords": ["change password"],
        "answer": "Go to **My Account → Change Password** to update your password.",
    },

    # --- Misc ---
    {
        "keywords": ["contact", "support", "help", "customer care", "talk to human"],
        "answer": "You can reach Cloots customer support at **support@cloots.com** or via the contact form on our website.",
    },
    {
        "keywords": ["coupon", "discount", "offer", "promo"],
        "answer": "Apply your coupon code in the **Cart** page before checkout — the discount will reflect in your total.",
    },
    {
        "keywords": ["size", "size chart", "size guide"],
        "answer": "Each product page has a **Size Chart** link below the size selector to help you pick the right fit.",
    },
    {
        "keywords": ["hi", "hello", "hey", "hii", "good morning", "good evening"],
        "answer": "Hi! 👋 I'm the Cloots assistant. Ask me anything about orders, shipping, payments, returns or product prices.",
    },
    {
        "keywords": ["thanks", "thank you", "thx"],
        "answer": "You're welcome! Happy shopping on Cloots 🛍️",
    },
    {
        "keywords": ["bye", "goodbye"],
        "answer": "Bye! Come back anytime — Cloots support is here 24/7.",
    },
]

FALLBACK = (
    "I'm not sure about that yet. You can ask me about:\n"
    "• How to place an order\n• Payment methods\n• Shipping & delivery time\n"
    "• Returns & refunds\n• Tracking your order\n• Price ranges (shirts, jeans, shoes, jackets)\n"
    "Or email **support@cloots.com** for personal help."
)


def answer_question(message: str) -> str:
    if not message:
        return "Please type a question and I'll help you out!"
    text = message.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    for entry in KB:
        for kw in entry["keywords"]:
            if kw in text:
                return entry["answer"]
    return FALLBACK


@csrf_exempt  # so the widget works without CSRF token wiring; remove if you wire CSRF
@require_POST
def ask(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        payload = {}
    message = (payload.get("message") or "").strip()
    return JsonResponse({"reply": answer_question(message)})
