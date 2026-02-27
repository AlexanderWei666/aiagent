"""工具模块：集中定义 Agent 可调用工具与默认工具集合。"""

import logging
from datetime import datetime
from typing import List

import requests
from langchain_core.tools import BaseTool
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

SUPPORTED_CITY_COORDS = {
    "成都": {"lat": 30.57, "lon": 104.06},
    "北京": {"lat": 39.90, "lon": 116.40},
    "上海": {"lat": 31.23, "lon": 121.47},
    "广州": {"lat": 23.12, "lon": 113.26},
    "深圳": {"lat": 22.54, "lon": 114.05},
    "杭州": {"lat": 30.27, "lon": 120.15},
    "西安": {"lat": 34.26, "lon": 108.94},
    "重庆": {"lat": 29.56, "lon": 106.55},
    "武汉": {"lat": 30.59, "lon": 114.30},
    "南京": {"lat": 32.04, "lon": 118.79},
}

WEATHER_CODE_MAP = {
    0: "晴朗",
    1: "多云",
    2: "阴天",
    3: "小雨",
    45: "雾",
    51: "小雨",
    61: "中雨",
    80: "阵雨",
}


@tool
def calculate(expression: str) -> str:
    """执行数学计算。注意：sin/cos/tan 默认使用弧度。"""
    try:
        logger.info(f"调用工具：calculate | 表达式: {expression}")
        allowed_names = {"__builtins__": {}}
        allowed_names.update(
            {
                "sin": __import__("math").sin,
                "cos": __import__("math").cos,
                "tan": __import__("math").tan,
                "sqrt": __import__("math").sqrt,
                "pi": __import__("math").pi,
            }
        )
        result = eval(expression, allowed_names)
        logger.info(f"计算结果：{result}")
        return str(result)
    except Exception as exc:
        logger.error(f"计算错误：{str(exc)}")
        return f"计算错误：{str(exc)}"


@tool
def get_current_time(format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前时间，格式化输出。"""
    try:
        logger.info(f"调用工具：get_current_time | 格式: {format_str}")
        return datetime.now().strftime(format_str)
    except Exception as exc:
        logger.error(f"时间格式错误：{str(exc)}")
        return f"时间格式错误：{str(exc)}"


@tool
def get_weather(city: str = "成都") -> str:
    """获取指定城市天气。仅支持预置城市列表。未指定城市时默认查询成都。"""
    try:
        logger.info(f"调用工具：get_weather | 城市: {city}")
        if city not in SUPPORTED_CITY_COORDS:
            supported = "、".join(SUPPORTED_CITY_COORDS.keys())
            logger.warning(f"不支持的城市: {city}")
            return f"抱歉，暂不支持查询 {city} 的天气。目前仅支持：{supported}"

        coords = SUPPORTED_CITY_COORDS[city]
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={coords['lat']}&longitude={coords['lon']}"
            "&current=temperature_2m,weathercode&timezone=Asia/Shanghai"
        )
        resp = requests.get(url, timeout=5).json()
        temp = resp["current"]["temperature_2m"]
        weather_code = resp["current"]["weathercode"]
        weather_desc = WEATHER_CODE_MAP.get(weather_code, "未知天气")
        return f"{city}当前天气：{weather_desc}，温度约 {temp}℃"
    except Exception as exc:
        logger.error(f"天气查询失败：{str(exc)}")
        return f"天气查询失败：{str(exc)}"


DEFAULT_TOOLS = (calculate, get_current_time, get_weather)


def get_default_tools() -> List[BaseTool]:
    """返回项目默认工具列表。"""
    return list(DEFAULT_TOOLS)
