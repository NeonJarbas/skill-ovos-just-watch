from ovos_utils import classproperty
from ovos_utils.log import LOG
from ovos_utils.ocp import MediaType, PlaybackType
from ovos_utils.parse import fuzzy_match, MatchStrategy
from ovos_utils.process_utils import RuntimeRequirements
from ovos_workshop.decorators.ocp import ocp_search
from ovos_workshop.skills.common_play import OVOSCommonPlaybackSkill
from simplejustwatchapi.justwatch import search


class JustWatchSkill(OVOSCommonPlaybackSkill):
    def __init__(self, *args, **kwargs):
        self.supported_media = [MediaType.MOVIE,
                                MediaType.VIDEO_EPISODES]
        super().__init__(*args, **kwargs)

    @classproperty
    def runtime_requirements(self):
        return RuntimeRequirements(internet_before_load=True,
                                   requires_internet=True)

    @property
    def allow_flatrate(self):
        # eg, Netflix
        return self.settings.get("flat_rate", True)

    @property
    def allow_rent(self):
        # eg, Apple TV
        return self.settings.get("rent", True)

    @property
    def allow_buy(self):
        # eg, Youtube
        return self.settings.get("buy", True)

    @property
    def allow_ads(self):
        # ad supported
        return self.settings.get("ads", True)

    @ocp_search()
    def search_db(self, phrase, media_type):
        if media_type == MediaType.MOVIE:
            return self._api_search(phrase, series=False)
        elif media_type == MediaType.VIDEO_EPISODES:
            return self._api_search(phrase, movies=False)
        else:
            return self._api_search(phrase)

    def _api_search(self, query, lang=None, country=None, movies=True, series=True):
        country = country or self.location.get("city", {}).get("state", {}).get("country", {}).get("code", "US")
        language = lang or self.lang.split("-")[0]

        results = search(title=query, country=country, language=language, best_only=True,
                         count=self.settings.get("max_results", 2))
        score = 1
        for r in results:
            if r.object_type == "MOVIE" and not movies:
                continue
            if r.object_type == "SHOW" and not series:
                continue
            seen = []
            for o in r.offers:
                if not o.url:
                    continue
                if o.monetization_type == "FLATRATE" and not self.allow_flatrate:
                    continue
                if o.monetization_type == "BUY" and not self.allow_buy:
                    continue
                if o.monetization_type == "RENT" and not self.allow_rent:
                    continue
                if o.monetization_type == "ADS" and not self.allow_ads:
                    continue
                if o.url in seen:
                    continue
                seen.append(o.url)
                yield {
                    "title": f"{r.title} [{o.monetization_type}] {o.name}",
                    "release_year": r.release_year,
                    "duration": r.runtime_minutes * 60,  # TODO is this in seconds?
                    "image": r.poster,
                    "match_confidence": fuzzy_match(r.title.lower(), query.lower(),
                                                    strategy=MatchStrategy.PARTIAL_TOKEN_SORT_RATIO) * score,
                    "skill_icon": o.icon,
                    "uri": o.url,
                    "skill_id": self.skill_id,
                    "media_type": MediaType.MOVIE if r.object_type == "MOVIE"
                    else MediaType.VIDEO_EPISODES,
                    "playback": PlaybackType.WEBVIEW
                }
            score -= 0.15


if __name__ == "__main__":
    from ovos_utils.messagebus import FakeBus

    LOG.set_level("DEBUG")

    s = JustWatchSkill(bus=FakeBus(), skill_id="t.fake")

    for r in s.search_db("casa de papel", MediaType.VIDEO_EPISODES):
        print(r)
        # {'title': 'Berlin [FLATRATE] Netflix', 'release_year': 2023, 'duration': 2880, 'image': 'https://images.justwatch.com/poster/310352436/s718/berlin.jpg', 'match_confidence': 0.5, 'skill_icon': 'https://images.justwatch.com/icon/207360008/s100/netflix.png', 'uri': 'http://www.netflix.com/title/81586657', 'skill_id': 't.fake', 'media_type': <MediaType.VIDEO_EPISODES: 19>, 'playback': <PlaybackType.WEBVIEW: 5>}
        # {'title': 'Money Heist [FLATRATE] Netflix', 'release_year': 2017, 'duration': 3000, 'image': 'https://images.justwatch.com/poster/249335581/s718/money-heist.jpg', 'match_confidence': 0.2833333333333334, 'skill_icon': 'https://images.justwatch.com/icon/207360008/s100/netflix.png', 'uri': 'http://www.netflix.com/title/80192098', 'skill_id': 't.fake', 'media_type': <MediaType.VIDEO_EPISODES: 19>, 'playback': <PlaybackType.WEBVIEW: 5>}
