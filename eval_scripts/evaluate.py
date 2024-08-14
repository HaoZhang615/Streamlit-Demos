import json
import logging
import time
from pathlib import Path
from io import BytesIO
import jmespath
import pandas as pd
import requests
from rich.progress import track
import streamlit as st
from . import service_setup
from .evaluate_metrics import metrics_by_name
import math


def send_question_to_target(
    question: str,
    url: str,
    parameters: dict = {},
    raise_error=False,
    response_answer_jmespath="message.content",
    response_context_jmespath="context.data_points.text",
):
    headers = {"Content-Type": "application/json"}
    body = {
        "messages": [{"content": question, "role": "user"}],
        "context": parameters,
    }
    try:
        r = requests.post(url, headers=headers, json=body)
        r.encoding = "utf-8"

        latency = r.elapsed.total_seconds()

        try:
            response_dict = r.json()
        except json.JSONDecodeError:
            raise ValueError(
                f"Response from target {url} is not valid JSON:\n\n{r.text} \n"
                "Make sure that your configuration points at a chat endpoint that returns a single JSON object.\n"
            )

        try:
            answer = jmespath.search(response_answer_jmespath, response_dict)
            data_points = jmespath.search(response_context_jmespath, response_dict)
            context = "\n\n".join(data_points)
        except Exception:
            raise ValueError(
                "Response does not adhere to the expected schema. "
                f"The answer should be accessible via the JMESPath expression '{response_answer_jmespath}' "
                f"and the context should be accessible via the JMESPath expression '{response_context_jmespath}'. "
                "Either adjust the app response or adjust send_question_to_target() in evaluate.py "
                f"to match the actual schema.\nResponse: {response_dict}"
            )

        response_obj = {"answer": answer, "context": context, "latency": latency}
        return response_obj
    except Exception as e:
        if raise_error:
            raise e
        return {
            "answer": str(e),
            "context": str(e),
            "latency": -1,
        }


def truncate_for_log(s: str, max_length=50):
    return s if len(s) < max_length else s[:max_length] + "..."

def load_jsonl(data: BytesIO) -> list[dict]:
    lines = data.readlines()
    return [json.loads(line.decode('utf-8')) for line in lines]

def clean_payload(data):
    if isinstance(data, dict):
        return {k: clean_payload(v) for k, v in data.items() if v is not None}
    elif isinstance(data, list):
        return [clean_payload(item) for item in data]
    elif isinstance(data, float) and math.isnan(data):
        return None
    else:
        return data

def run_evaluation(
    openai_config: dict,
    target_url: str,
    test_data_BytesIO: BytesIO,
    requested_metrics: list,
    target_parameters: dict,
    num_questions=None,
    target_response_answer_jmespath="message.content",
    target_response_context_jmespath="context.data_points.text",
):
    
    testdata = load_jsonl(test_data_BytesIO)

    st.write("Sending a test question to the target to ensure it is running...")
    try:
        question = "Who are you?"
        target_data = send_question_to_target(
            question,
            target_url,
            target_parameters,
            raise_error=True,
            response_answer_jmespath=target_response_answer_jmespath,
            response_context_jmespath=target_response_context_jmespath,
        )
        st.write(
            'Successfully received response from target for question: "%s"\n"answer": "%s"\n"context": "%s"',
            truncate_for_log(question),
            truncate_for_log(target_data["answer"]),
            truncate_for_log(target_data["context"]),
        )
    except Exception as e:
        st.write("Failed to send a test question to the target due to error: \n%s", e)
        print("Failed to send a test question to the target due to error: \n%s", e)
        return False

    st.write("Sending a test chat completion to the GPT deployment to ensure it is running...")
    try:
        gpt_response = service_setup.get_openai_client(openai_config).chat.completions.create(
            model=openai_config.model,
            messages=[{"role": "user", "content": "Hello!"}],
            n=1,
        )
        st.write('Successfully received response from GPT: "%s"', gpt_response.choices[0].message.content)
        print('Successfully received response from GPT: "%s"', gpt_response.choices[0].message.content)
    except Exception as e:
        st.write("Failed to send a test chat completion to the GPT deployment due to error: \n%s", e)
        print("Failed to send a test chat completion to the GPT deployment due to error: \n%s", e)
        return False

    st.write("Starting evaluation...")
    print("Starting evaluation...")

    for metric in requested_metrics:
        # if isinstance(metric, list) and len(metric) == 1:
        #     metric = metric[0]
        # if not isinstance(metric, str):
        #     st.write(f"Invalid metric type: {type(metric)}. Metrics should be strings.")
        #     print(metric)
        #     print(f"Invalid metric type: {type(metric)}. Metrics should be strings.")
        #     return False
        if metric not in metrics_by_name:
            st.write(f"Requested metric {metric} is not available. Available metrics: {metrics_by_name.keys()}")
            print(f"Requested metric {metric} is not available. Available metrics: {metrics_by_name.keys()}")
            return False

    requested_metrics = [
        metrics_by_name[metric_name] for metric_name in requested_metrics if metric_name in metrics_by_name
    ]

    def evaluate_row(row):
        output = {}
        output["question"] = row["question"]
        output["truth"] = row["truth"]
        target_response = send_question_to_target(
            question=row["question"],
            url=target_url,
            parameters=target_parameters,
            response_answer_jmespath=target_response_answer_jmespath,
            response_context_jmespath=target_response_context_jmespath,
        )
        output.update(target_response)
        for metric in requested_metrics:
            result = metric.evaluator_fn(openai_config=openai_config)(
                question=row["question"],
                answer=output["answer"],
                context=output["context"],
                ground_truth=row["truth"],
            )
            output.update(result)

        return output

    # Run evaluations in serial and collect results in a list
    questions_with_ratings = []
    for row in track(testdata, description="Processing..."):
        questions_with_ratings.append(evaluate_row(row))
    num_questions = len(questions_with_ratings)
    st.write("Evaluation calls have completed. Calculating overall metrics now...")
    print("Evaluation calls have completed. Calculating overall metrics now...")

    # Calculate aggregate metrics
    metrics_summary = {}
    df = pd.DataFrame(questions_with_ratings)
    eval_results = {
        "evaluation_gpt_model": openai_config.model,
        "evaluation_timestamp": int(time.time()),
        "target_url": target_url,
        "target_parameters": target_parameters,
        "num_questions": num_questions,
        "line_evaluations": questions_with_ratings
        }
    for metric in requested_metrics:
        metrics_summary[metric.METRIC_NAME] = metric.get_aggregate_stats(df)
    eval_results["metrics_summary"] = metrics_summary
    # Clean the payload
    eval_results = clean_payload(eval_results)
    return eval_results

