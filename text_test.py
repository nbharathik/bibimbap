import os
import re
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
from typing import Optional, Dict, Union

# Load API key from .env
load_dotenv()

class VQAEvaluator:
    def __init__(self, questions_csv_path: str = "./data/vision_questions.csv"):
        """
        Initializes the evaluator by loading the ground truth data.
        """
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Load the CSV into a dictionary for fast lookup by Question ID or Question Text
        # Assumes CSV columns: 'question_id', 'question', 'answer_type', 'expected_answer'
        try:
            df = pd.read_csv(questions_csv_path)
            # Normalize column names
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
            self.ground_truth_data = df.to_dict(orient="records")
        except FileNotFoundError:
            raise Exception(f"Questions file not found at {questions_csv_path}")

    # --- NUMERIC LOGIC (The "Hard" Tolerance) ---
    
    def _extract_numeric_value(self, text: Union[str, float, int]) -> Optional[float]:
        """Parses the first numeric value found in the text."""
        if isinstance(text, (int, float)):
            return float(text)
        
        # Regex to find integer or float (handles 10, 10.5, -5)
        match = re.search(r"-?\d+(\.\d+)?", str(text))
        return float(match.group()) if match else None

    def _check_numeric_tolerance(self, predicted: float, expected: float, 
                               abs_tol: float = 0.1, rel_tol: float = 0.001) -> bool:
        """
        Standard numeric tolerance check.
        Returns True if abs(a-b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)
        """
        diff = abs(predicted - expected)
        # Python's math.isclose logic manually implemented for clarity
        tolerance = max(rel_tol * max(abs(predicted), abs(expected)), abs_tol)
        return diff <= tolerance

    # --- TEXT LOGIC (The "LLM" Tolerance) ---

    def _check_text_tolerance(self, question: str, expected: str, predicted: str) -> bool:
        """
        Uses LLM-as-a-Judge to check 'Semantic Tolerance'.
        Just as 17.1 is 'close enough' to 17.11 numerically,
        'Pale Yellow' is 'close enough' to 'Yellow' semantically.
        """
        # 1. Quick exact match check (save API cost)
        if str(predicted).strip().lower() == str(expected).strip().lower():
            return True

        # 2. LLM Judge
        prompt = f"""
        You are an automated evaluator for a Visual QA system. 
        Your job is to determine if the ACTUAL OUTPUT is semantically equivalent to the EXPECTED OUTPUT.
        
        Question: {question}
        Expected Output: {expected}
        Actual Output: {predicted}
        
        Criteria for "Pass":
        - Synonyms are acceptable (e.g., "Sofa" == "Couch").
        - Specificity is acceptable (e.g., "Pale Yellow" matches "Yellow").
        - Extra verbiage is acceptable (e.g., "I see a chair" matches "Chair").
        - Directional opposites are FAILures (e.g., "Left" != "Right").
        
        Reply strictly with a JSON object: {{"within_tolerance": true}} or {{"within_tolerance": false}}
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            return result.get("within_tolerance", False)
            
        except Exception as e:
            print(f"LLM Judge Error: {e}")
            return False

    # --- MAIN EXECUTION FUNCTION ---

    def execute_test(self, question_text: str, model_output: str) -> Dict[str, bool]:
        """
        Main entry point. Finds the ground truth for the question and runs the appropriate check.
        """
        # 1. Lookup Ground Truth
        # We search the loaded CSV data for the matching question
        row = next((item for item in self.ground_truth_data if item["question"] == question_text), None)
        
        if not row:
            return {"error": "Question not found in ground truth CSV"}

        expected_val = row.get("expected_answer") or row.get("ground_truth")
        answer_type = row.get("answer_type", "Text") # Default to Text if column missing

        # 2. Branch Logic
        if str(answer_type).lower() == "number":
            # NUMERIC CHECK
            pred_num = self._extract_numeric_value(model_output)
            exp_num = self._extract_numeric_value(expected_val)
            
            if pred_num is None or exp_num is None:
                return {"within_tolerance": False, "reason": "Could not parse number"}
            
            # You can tune tolerances here or pass them in
            is_ok = self._check_numeric_tolerance(pred_num, exp_num, abs_tol=0.5) 
            return {"within_tolerance": is_ok, "type": "number"}

        else:
            # TEXT CHECK (LLM Judge)
            is_ok = self._check_text_tolerance(question_text, str(expected_val), str(model_output))
            return {"within_tolerance": is_ok, "type": "text"}

# --- USAGE EXAMPLE ---
if __name__ == "__main__":
    # Simulate the testing process
    evaluator = VQAEvaluator("./data/vision_questions.csv")

    # Example 1: Numeric Test
    q1 = "How many chairs are there?"
    output1 = "There are 8 chairs." # Model output
    result1 = evaluator.execute_test(q1, output1)
    print(f"Q: {q1} | Result: {result1}")

    # Example 2: Text Test
    q2 = "What color are the chairs?"
    output2 = "They are a light pastel yellow." # Model output
    result2 = evaluator.execute_test(q2, output2)
    print(f"Q: {q2} | Result: {result2}")