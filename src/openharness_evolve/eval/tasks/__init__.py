from openharness_evolve.eval.tasks.code_generation import get_code_generation_tasks
from openharness_evolve.eval.tasks.file_manipulation import get_file_manipulation_tasks
from openharness_evolve.eval.tasks.debugging import get_debugging_tasks


def get_all_tasks():
    return get_code_generation_tasks() + get_file_manipulation_tasks() + get_debugging_tasks()


def get_task_suite(name: str = "default"):
    if name == "default":
        return get_all_tasks()
    if name == "code_generation":
        return get_code_generation_tasks()
    if name == "file_manipulation":
        return get_file_manipulation_tasks()
    if name == "debugging":
        return get_debugging_tasks()
    raise ValueError(f"Unknown task suite: {name}")
