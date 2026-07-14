#!/usr/bin/env python3
"""scene_config.py — V10：场景化 LLM 配置加载器。

从 config/scenes.yaml 加载场景配置，支持环境变量覆盖。
借鉴 Dayu 的 prompts/manifests/*.json，但简化为纯参数化（无工具选择、无 fragment assembly）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import yaml


@dataclass
class SceneConfig:
    """单个场景的 LLM 配置。

    Args:
        name: 场景名称（write/audit/repair/overview/decision/evidence）。
        model: 模型标识符（default 表示使用系统默认）。
        temperature: LLM 温度参数。
        max_tokens: 最大输出 token 数。
        description: 场景用途说明。
    """

    name: str
    model: str = "default"
    temperature: float = 0.3
    max_tokens: int = 8192
    description: str = ""

    def resolve_model(self, default_model: str = "") -> str:
        """解析实际使用的模型名称。

        优先级：环境变量 > 配置文件 > 传入的默认值。

        Args:
            default_model: 系统默认模型。

        Returns:
            解析后的模型名称。
        """
        env_key = f"TURTLE_MODEL_{self.name.upper()}"
        env_model = os.environ.get(env_key)
        if env_model:
            return env_model
        if self.model and self.model != "default":
            return self.model
        return default_model

    def resolve_temperature(self) -> float:
        """解析实际使用的温度参数。

        优先级：环境变量 > 配置文件。

        Returns:
            解析后的温度值。
        """
        env_key = f"TURTLE_TEMP_{self.name.upper()}"
        env_val = os.environ.get(env_key)
        if env_val is not None:
            try:
                return float(env_val)
            except ValueError:
                pass
        return self.temperature

    def resolve_max_tokens(self) -> int:
        """解析实际使用的最大 token 数。

        优先级：环境变量 > 配置文件。

        Returns:
            解析后的最大 token 数。
        """
        env_key = f"TURTLE_MAX_TOKENS_{self.name.upper()}"
        env_val = os.environ.get(env_key)
        if env_val is not None:
            try:
                return int(env_val)
            except ValueError:
                pass
        return self.max_tokens


def load_scenes(config_path: str | None = None) -> dict[str, SceneConfig]:
    """加载场景配置。

    Args:
        config_path: scenes.yaml 的路径。若为 None，则使用默认路径。

    Returns:
        场景名称到 SceneConfig 的映射。

    Raises:
        FileNotFoundError: 配置文件不存在。
        yaml.YAMLError: YAML 解析失败。
    """
    if config_path is None:
        # 默认路径：scripts/../config/scenes.yaml
        scripts_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(scripts_dir)
        config_path = os.path.join(root_dir, "config", "scenes.yaml")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"场景配置文件不存在: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError("scenes.yaml 必须为顶层映射")

    scenes: dict[str, SceneConfig] = {}
    for name, data in raw.items():
        if not isinstance(data, dict):
            continue
        scenes[name] = SceneConfig(
            name=str(name),
            model=str(data.get("model", "default")),
            temperature=float(data.get("temperature", 0.3)),
            max_tokens=int(data.get("max_tokens", 8192)),
            description=str(data.get("description", "")),
        )

    return scenes


def get_scene_config(scene_name: str, config_path: str | None = None) -> SceneConfig:
    """获取单个场景配置。

    Args:
        scene_name: 场景名称。
        config_path: scenes.yaml 路径。

    Returns:
        SceneConfig 对象。若场景不存在，返回默认配置。
    """
    try:
        scenes = load_scenes(config_path)
    except (FileNotFoundError, yaml.YAMLError, ValueError):
        scenes = {}

    return scenes.get(scene_name, SceneConfig(name=scene_name))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="加载并显示场景配置")
    ap.add_argument("--scene", "-s", help="显示指定场景的配置")
    ap.add_argument("--config", "-c", help="scenes.yaml 路径")
    args = ap.parse_args()

    try:
        scenes = load_scenes(args.config)
    except Exception as e:
        print(f"❌ 加载场景配置失败: {e}", file=sys.stderr)
        sys.exit(1)

    if args.scene:
        sc = scenes.get(args.scene)
        if not sc:
            print(f"❌ 未知场景: {args.scene}", file=sys.stderr)
            sys.exit(1)
        print(f"场景: {sc.name}")
        print(f"  模型: {sc.resolve_model()}")
        print(f"  温度: {sc.resolve_temperature()}")
        print(f"  最大Token: {sc.resolve_max_tokens()}")
        print(f"  说明: {sc.description}")
    else:
        print(f"已加载 {len(scenes)} 个场景:")
        for name, sc in scenes.items():
            print(f"  {name}: model={sc.model}, temp={sc.temperature}, max_tokens={sc.max_tokens}")
