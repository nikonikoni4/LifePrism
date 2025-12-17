from lifewatch.llm.llm_classify.schemas import classifyStateLogitems,classifyState
import functools
def test_for_llm_class_state(test_flag : bool):
    """
    graph.invoke的state变量名应该为main_state
    """
    def print_for_state(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if test_flag:
                if len(args) >= 2:
                    input_data = args[1]
                    if isinstance(input_data, classifyStateLogitems):
                        single_len = len(input_data.log_items_for_single) if input_data.log_items_for_single else 0
                        multi_len = len(input_data.log_items_for_multi) if input_data.log_items_for_multi else 0
                        multi_short_len = len(input_data.log_items_for_multi_short) if input_data.log_items_for_multi_short else 0
                        multi_long_len = len(input_data.log_items_for_multi_long) if input_data.log_items_for_multi_long else 0
                        print(f"{func.__name__}: 输入数据长度 - single: {single_len}, multi: {multi_len}, multi_short: {multi_short_len}, multi_long: {multi_long_len}")
                    elif isinstance(input_data, classifyState):
                        length = len(input_data.log_items) if input_data.log_items else 0
                        print(f"{func.__name__}: 输入数据长度 {length}")
                result = func(*args, **kwargs)
                if isinstance(result, dict):
                    print(f"{func.__name__}:当前函数输出result_items:{result.get("result_items",None)}")
                print(f"{func.__name__}:当前函数输出结果类型:{type(result)}")
                return result
            else: 
                return func(*args, **kwargs)
        return wrapper
    return print_for_state
