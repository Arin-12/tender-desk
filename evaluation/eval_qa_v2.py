
"""
Improved QA evaluation harness (v2).

Usage:
    python -m evaluation.eval_qa_v2 <doc_id> evaluation/eval_set_2tenders_30q.json --k 6

Important:
    Run separately for each tender.
    The dataset must be filtered to questions belonging to that document,
    or each question must contain a matching doc_id field.
"""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

from rag.pipeline import run_rag_pipeline


def norm(value):
    return str(value).lower().replace(",", "").strip()


def normalize_pages(pages):
    result = set()

    for page in pages:
        try:
            result.add(int(page))
        except (TypeError, ValueError):
            continue

    return result


def get_confidence(result):
    confidence = result.get("confidence", {})

    if isinstance(confidence, dict):
        return confidence.get("score")

    return confidence


def check_answer(item, answer):
    """
    Avoid vacuous passes when expected_contains is empty.
    """
    expected = item.get("expected_contains", [])

    if not expected:
        return None

    normalized_answer = norm(answer)

    return all(norm(value) in normalized_answer for value in expected)


def evaluate_citations(expected_pages, cited_pages):
    """
    Citation precision = relevant cited pages / all cited pages
    Citation recall = relevant cited pages / expected evidence pages

    Strict citation correctness requires every cited page to be relevant
    and at least one citation to be present.
    """
    if not expected_pages:
        return None, None, None

    if not cited_pages:
        return 0.0, 0.0, False

    relevant = expected_pages & cited_pages

    precision = len(relevant) / len(cited_pages)
    recall = len(relevant) / len(expected_pages)

    strict_correct = cited_pages.issubset(expected_pages)

    return precision, recall, strict_correct


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: python -m evaluation.eval_qa_v2 "
            "<doc_id> <eval_set.json> [--k 6]"
        )
        sys.exit(1)

    doc_id = sys.argv[1]
    dataset_path = Path(sys.argv[2])

    k = (
        int(sys.argv[sys.argv.index("--k") + 1])
        if "--k" in sys.argv
        else 6
    )

    items = json.loads(dataset_path.read_text(encoding="utf-8"))

    # If the dataset has doc_id fields, select only this document's questions.
    if items and "tender_id" in items[0]:
        items = [item for item in items if item["tender_id"] == doc_id]

    if not items:
        print(f"No questions found for document: {doc_id}")
        sys.exit(1)

    rows = []

    answer_scores = []
    citation_precisions = []
    citation_recalls = []
    strict_citation_scores = []
    confidence_scores = []

    for index, item in enumerate(items, start=1):
        question = item["question"]

        print(f"\n[{index}/{len(items)}] {question}")

        try:
            result = run_rag_pipeline(question, doc_id, k)

            answer = result.get("answer", "")
            answer_correct = check_answer(item, answer)

            cited_pages = normalize_pages(
                source.get("page")
                for source in result.get("sources", [])
            )

            expected_pages = normalize_pages(
                item.get("relevant_pages")
                or item.get("expected_pages", [])
            )

            citation_precision, citation_recall, citation_correct = (
                evaluate_citations(expected_pages, cited_pages)
            )

            confidence = get_confidence(result)

            if answer_correct is not None:
                answer_scores.append(int(answer_correct))

            if citation_precision is not None:
                citation_precisions.append(citation_precision)
                citation_recalls.append(citation_recall)
                strict_citation_scores.append(int(citation_correct))

            if confidence is not None:
                confidence_scores.append(float(confidence))

            rows.append({
                "id": item.get("id", ""),
                "tender_id": item.get("tender_id", doc_id),
                "tender_name": item.get("tender_name", ""),
                "question": question,
                "question_type": item.get("question_type", ""),
                "answer_correct": answer_correct,
                "citation_correct": citation_correct,
                "citation_precision": citation_precision,
                "citation_recall": citation_recall,
                "expected_pages": ",".join(map(str, sorted(expected_pages))),
                "cited_pages": ",".join(map(str, sorted(cited_pages))),
                "confidence": confidence,
                "answer": answer[:500],
            })

            print(f"Answer correct     : {answer_correct}")
            print(f"Cited pages        : {sorted(cited_pages)}")
            print(f"Expected pages     : {sorted(expected_pages)}")
            print(f"Citation precision : {citation_precision}")
            print(f"Citation recall    : {citation_recall}")
            print(f"Strict citation    : {citation_correct}")

        except Exception as error:
            print(f"ERROR: {error}")

            rows.append({
                "doc_id": doc_id,
                "question": question,
                "question_type": item.get("question_type", ""),
                "error": str(error),
            })

    def mean(values):
        return sum(values) / len(values) if values else None

    print("\n" + "=" * 55)
    print("QA EVALUATION SUMMARY")
    print("=" * 55)

    print(f"Document ID             : {doc_id}")
    print(f"Questions               : {len(items)}")
    print(f"Answer accuracy         : {mean(answer_scores)}")
    print(f"Citation precision      : {mean(citation_precisions)}")
    print(f"Citation recall         : {mean(citation_recalls)}")
    print(f"Strict citation accuracy: {mean(strict_citation_scores)}")
    print(f"Mean confidence         : {mean(confidence_scores)}")

    output_dir = Path("evaluation")
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_path = (
        output_dir /
        f"results_v2_{doc_id}_k{k}_{timestamp}.csv"
    )

    fieldnames = list(dict.fromkeys(
        key for row in rows for key in row
    ))

    with output_path.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved results: {output_path}")


if __name__ == "__main__":
    main()
