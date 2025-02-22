import time
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from retry import retry
from requests.exceptions import ConnectionError, Timeout


class TokenNotFoundError(Exception):
    pass


class TabelogClient:
    def __init__(self, url: str, ua: str):
        self.base_url = url
        self.ua = ua
        self.session = requests.Session()

    def _get_page_soup(self, url: str) -> BeautifulSoup:
        """指定URLのページを取得し、BeautifulSoupオブジェクトに変換して返す"""
        response = self.session.get(url)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")

    def _get_csrf_token(self, bs: BeautifulSoup) -> str:
        """BeautifulSoupオブジェクトからCSRFトークンを抽出する"""
        token_elm = bs.select_one("#form_authenticity_token")
        if token_elm is None:
            raise TokenNotFoundError("CSRFトークンが見つかりません")
        return token_elm.get("data-stable_token")

    @retry(exceptions=(ConnectionError, Timeout), tries=3, delay=3, backoff=2)
    def _fetch_review_more(self, token: str, review_id: int) -> str:
        """
        review_idを元に「more」ページを取得し、本文を返す
        ConnectionError, Timeoutが発生した場合、自動でリトライする
        """
        time.sleep(1)
        url = "https://tabelog.com/restaurant_detail_review/review_more"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Csrf-Token": token,
            "x-requested-with": "XMLHttpRequest",
        }
        response = self.session.post(
            url, headers=headers, data={"review_id": review_id}, timeout=10
        )
        response.raise_for_status()  # エラー発生時は例外が投げられ、retryされる
        html = response.json().get("html", "")
        more_bs = BeautifulSoup(html, "lxml")
        text_elm = more_bs.select_one(
            "div.rvw-item__rvw-comment.rvw-item__rvw-comment--custom p"
        )
        if text_elm:
            return text_elm.get_text(strip=True)
        return ""

    def _get_next_page_url(self, bs: BeautifulSoup, current_url: str) -> str:
        """次ページのURLを抽出（存在しなければNoneを返す）"""
        next_elm = bs.select_one("a.c-pagination__arrow.c-pagination__arrow--next")
        if next_elm:
            parsed_url = urlparse(current_url)
            url_path = next_elm["href"].strip("/")
            return f"{parsed_url.scheme}://{parsed_url.netloc}/{url_path}"
        return None

    def get_reviews(self) -> pd.DataFrame:
        """全ページのレビューを取得してDataFrameとして返す"""
        reviews_data = []
        current_url = self.base_url

        while current_url is not None:
            print(f"処理中のURL: {current_url}")
            bs = self._get_page_soup(current_url)
            token = self._get_csrf_token(bs)

            review_items = bs.select("div.rvw-item.js-rvw-item-clickable-area")
            for review_elm in review_items:
                js_vote_interest = review_elm.select_one("div.js-vote-interest")
                review_id = js_vote_interest.get("data-review-id")
                if review_id is None:
                    continue
                review_text = self._fetch_review_more(token, int(review_id))
                if review_text:
                    reviews_data.append({"review_id": review_id, "text": review_text})
            next_url = self._get_next_page_url(bs, current_url)
            current_url = next_url
        return pd.DataFrame(reviews_data)
