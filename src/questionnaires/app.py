from pathlib import Path

import yaml
from flask import Flask, redirect, render_template, request, url_for

from src.log_config import configure_logging
from src.questionnaires.functions import save_results, score_results

configure_logging()

scale = "bdi"

app = Flask(__name__)

with open(f"src/questionnaires/inventory/{scale}.yaml", "r") as file:
    questionnaire = yaml.safe_load(file)


@app.route("/", methods=["GET", "POST"])
def survey():
    if request.method == "POST":
        answers = request.form
        score = score_results(scale, answers)
        save_results(scale, questionnaire, answers, score)
        return redirect(url_for("thank_you"))
    return render_template(
        f"{scale}.html",
        questions=questionnaire["questions"],
        options=questionnaire["options"] if "options" in questionnaire else None,
        title=questionnaire["title"] if "title" in questionnaire else None,
        instructions=questionnaire["instructions"]
        if "instructions" in questionnaire
        else None,
    )


@app.route("/thank_you")
def thank_you():
    return "Thank you for completing the survey!"


if __name__ == "__main__":
    app.run(debug=True)
