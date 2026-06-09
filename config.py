import os


class Config:

    def __init__(self):
        self.env = os.getenv("env")
        self.HEADERS = {
            "x-api-key": "1111",
            "Access-Token": "AKIA4MTWHCUGXSASXZJP",
            "Content-Type": "application/json",
        }
        print(f"{self.env} LMS DB...")

        if self.env == "DEV":
            self.SAVE_URL = "http://aeon-lms-alb-an1-dev-1015334905.ap-northeast-1.elb.amazonaws.com/visualization/create_lesson_evaluation"
            self.PREPROCESSING_URL = "http://net20240020-svc.inference.svc:8000/process"
            self.EXTRACT_EVAL_URL = "http://net20250008-svc.inference.svc:8000/evaluate"
        # elif self.env == "STG":
        #     self.SAVE_URL = "http://aeon-lms-alb-an1-prd-test-1264392184.ap-northeast-1.elb.amazonaws.com/visualization/create_lesson_evaluation"
        #     self.PREPROCESSING_URL = "http://net20240020-svc.inference.svc:8000/process"
        #     self.EXTRACT_EVAL_URL = "http://net20250008-svc.inference.svc:8000/evaluate"
        elif self.env == "STG":
            self.SAVE_URL = "https://jp-api-test.aeonmystyle.com/visualization/create_lesson_evaluation"
            self.PREPROCESSING_URL = "http://net20240020-svc.inference.svc:8000/process"
            self.EXTRACT_EVAL_URL = "http://net20250008-svc.inference.svc:8000/evaluate"
        elif self.env == "PROD":
            self.SAVE_URL = "http://aeon-lms-alb-an1-prd-435572520.ap-northeast-1.elb.amazonaws.com/visualization/create_lesson_evaluation"
            self.PREPROCESSING_URL = (
                "http://net20250052-svc.inference.svc:8000/process"  # net20250052
            )
            self.EXTRACT_EVAL_URL = (
                "http://net20250050-svc.inference.svc:8000/evaluate"  # net20250050
            )


if __name__ == "__main__":
    config = Config()
    # print(config.env)
    # print(config.HEADERS)
    print(config.SAVE_URL)
    print(config.PREPROCESSING_URL)
    print(config.EXTRACT_EVAL_URL)
