# Custom Inference System Manual

This manual explains how to create a custom Text-to-BIM inference system using `inference/base_class.py` and `inference/custom.py`.

## 1) Understand the base class
`inference/base_class.py` defines an abstract class `TextToBIM` with a required method:

- `invoke(prompt, ifc_path, output_format)`

Your custom class must implement this method. It receives:

- `prompt`: the question from the benchmark CSV
- `ifc_path`: path to the IFC file that must be edited
- `output_format`: `None` or a Pydantic model class for information retrieval that you should return

Your class may also use:

- `self.llm_system_prompt`: populated from `system_prompt` in the config
- `self.model_name`: populated from `model_name` in the config
- `self.input_tokens` / `self.output_tokens`: optional fields you can fill in

## 2) Create or edit your custom class
The default template is in `inference/custom.py` and looks like this:

```python
from base_class import TextToBIM
from pydantic import BaseModel

class CustomTextToBIM(TextToBIM):

    def __init__(self, system_prompt: str | None = None, model_name: str | None = None):
        """Initialize your Custom TextToBIM system here."""
        super().__init__(system_prompt=system_prompt, model_name=model_name)

    def invoke(self, prompt: str, ifc_path: str, output_format: type[BaseModel] | None) -> str | BaseModel:
        """This method must edit the ifc file and return the model output in the specified format (String or Pydantic Model)."""
```

Implement your logic inside `invoke`:

1. Load and edit the IFC file located at `ifc_path`.
2. Run your inference logic (LLM, rules, etc.).
3. Return either:
   - a `str` if `output_format` is `None`, or
   - an instance of the provided Pydantic model if `output_format` is not `None`.

## 3) Reference your class from the config
Set `inference_system` in your config JSON. Examples:

```json
{
  "inference_system": "custom:CustomTextToBIM"
}
```

Short form resolves inside `inference/`, so `custom:CustomTextToBIM` loads `inference/custom.py`.

You can also reference a file path or module:

```json
{
  "inference_system": "inference/custom.py:CustomTextToBIM"
}
```

## 4) Run the benchmark
Example command:

```bash
python inference_benchmark.py --config configs/your-config.json
```

The runner will instantiate your class with:

- `system_prompt` from the config (if provided)
- `model_name` from the config (if provided)

## 5) Minimal implementation example
Below is a minimal (non-functional) structure that shows the flow:

```python
from base_class import TextToBIM
from pydantic import BaseModel

class CustomTextToBIM(TextToBIM):
   def __init__(self, system_prompt: str | None = None, model_name: str | None = None):
        # Calling the base class constructor makes the system prompt, model name 
        # and input/output tokens available as class attributes 
        # (i.e. self.system_prompt, self.model_name, self.input_tokens, self.output_tokens)
        super().__init__(system_prompt=system_prompt, model_name=model_name)
        
    def invoke(self, prompt: str, ifc_path: str, output_format: type[BaseModel] | None):
        # 1) Read / modify the IFC file on disk at ifc_path
        # 2) Produce your answer
        result_text = "example output"

        if output_format is None:
            return result_text

        # When output_format is provided, return a Pydantic instance
        return output_format(output=result_text)
```

## 6) Notes and best practices
- The `invoke` method should edit the ifc file on disk at the provided `ifc_path`.
- Keep the class constructor signature compatible with `TextToBIM`.
- If you create another file in `inference/`, you can reference it in the config using `your_file:YourClass`.
- Use `self.input_tokens` and `self.output_tokens` if you want the runner to record token usage.
