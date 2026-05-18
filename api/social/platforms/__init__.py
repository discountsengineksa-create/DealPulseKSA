"""قائمة كل posters المسجّلة — الـ dispatcher يدور عليها بالترتيب."""
from api.social.platforms.discord import DiscordPoster
from api.social.platforms.facebook import FacebookPoster
from api.social.platforms.instagram import InstagramPoster
from api.social.platforms.linkedin import LinkedInPoster
from api.social.platforms.pinterest import PinterestPoster
from api.social.platforms.telegram_ch import TelegramChannelPoster
from api.social.platforms.threads import ThreadsPoster
from api.social.platforms.x_twitter import XTwitterPoster

# الترتيب يحدد ترتيب النشر — السهلة أولاً
REGISTERED_POSTERS = [
    DiscordPoster,
    TelegramChannelPoster,
    XTwitterPoster,
    FacebookPoster,
    InstagramPoster,
    ThreadsPoster,
    PinterestPoster,
    LinkedInPoster,
]
