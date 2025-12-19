import logging
# logging全局唯一配置
logging.basicConfig(
    level = logging.INFO,
    format = "%(levelname)s %(filename)s func:%(funcName)s line %(lineno)d : %(message)s"
) # 暂时固定设置，后续增加config内容

def get_logger(name:str,level=None)->logging.Logger:
    """
    args:
        name: 输入logger名称
        level: 输出等级

    """

    logger = logging.getLogger(name)
    if level:
        logger.setLevel(level)
    return logger