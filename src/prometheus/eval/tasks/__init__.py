from prometheus.eval.tasks.code_generation import get_code_generation_tasks
from prometheus.eval.tasks.file_manipulation import get_file_manipulation_tasks
from prometheus.eval.tasks.debugging import get_debugging_tasks
from prometheus.eval.tasks.reasoning import get_reasoning_tasks


def get_all_tasks():
    return (
        get_code_generation_tasks()
        + get_file_manipulation_tasks()
        + get_debugging_tasks()
        + get_reasoning_tasks()
    )


def get_task_suite(name: str = "default"):
    suites = {
        "default": get_all_tasks,
        "code_generation": get_code_generation_tasks,
        "file_manipulation": get_file_manipulation_tasks,
        "debugging": get_debugging_tasks,
        "reasoning": get_reasoning_tasks,
    }
    if name not in suites:
        raise ValueError(f"Unknown task suite: {name}")
    return suites[name]()
