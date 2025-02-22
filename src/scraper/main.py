import os

import fire

from libs.tabelog import TabelogClient


def proc(
    url: str,
    ua: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
):
    tc = TabelogClient(url, ua)
    df = tc.get_reviews()
    output_dir = os.path.join("data", "input_data")
    os.makedirs(output_dir, exist_ok=True)
    df.to_csv(os.path.join(output_dir, "reviews.csv"), index=False)


def main():
    fire.Fire(proc)


if __name__ == "__main__":
    main()
