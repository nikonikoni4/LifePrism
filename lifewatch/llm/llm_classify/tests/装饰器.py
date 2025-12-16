# 第一层：接收装饰器参数
def log_with_msg(message):
    # 第二层：接收原函数
    def decorator(func):
        # 第三层：替换原函数
        def wrapper(*args, **kwargs):
            print(f"[{message}] 开始...")  # 使用你传入的 message
            result = func(*args, **kwargs)
            print(f"[{message}] 结束。{result}")
            return result
        return wrapper
    return decorator
# --- 使用方式 ---
@log_with_msg("数据计算")  # 在这里传入你想打印的内容
def calculate_sum(a, b):
    return a + b
calculate_sum(1,2)

