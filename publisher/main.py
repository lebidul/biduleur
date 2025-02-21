from daily_post import publish_daily_post
from agenda import publish_agenda
import sys


def main(daily_post=True, instagram_post=False, update_agenda=False, local_env=True):
    # print("Environment Variables:")
    # for key, value in os.environ.items():
    #     print(f"{key}: {value}")

    # username = os.getenv("INSTAGRAM_USERNAME")
    # password = os.getenv("INSTAGRAM_PASSWORD")
    #
    # if not username or not password:
    #     print("Error: Environment variables not set!")
    #     return

    if daily_post:
        publish_daily_post(instagram_post=instagram_post, local_env=local_env)

    if update_agenda:
        publish_agenda()

if __name__ == "__main__":
    instagram_post = "--post-to-instagram" in sys.argv
    update_agenda = "--update-agenda" in sys.argv
    local_env =  "--local-env" in sys.argv
    main(instagram_post, update_agenda, local_env)
