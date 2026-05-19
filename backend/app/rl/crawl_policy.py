from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CrawlAction(str, Enum):
    continue_domain = "continue_domain"
    pause_domain = "pause_domain"
    switch_proxy = "switch_proxy"
    switch_render_mode = "switch_render_mode"
    lower_concurrency = "lower_concurrency"
    prioritize_url = "prioritize_url"
    stop_domain = "stop_domain"


@dataclass(frozen=True)
class CrawlState:
    depth: int
    latency_ms: float
    http_status: int | None
    extraction_yield: float
    content_novelty: float
    error_rate: float
    captcha_detected: bool
    robots_allowed: bool


def reward(state: CrawlState) -> float:
    value = 2.0 * state.extraction_yield + state.content_novelty
    value -= min(state.latency_ms / 10_000, 2.0)
    value -= 2.5 * state.error_rate
    if state.captcha_detected:
        value -= 3.0
    if not state.robots_allowed:
        value -= 10.0
    return value


def safe_default_policy(state: CrawlState) -> CrawlAction:
    if not state.robots_allowed:
        return CrawlAction.stop_domain
    if state.captcha_detected:
        return CrawlAction.pause_domain
    if state.error_rate > 0.25:
        return CrawlAction.lower_concurrency
    if state.extraction_yield < 0.05 and state.depth > 2:
        return CrawlAction.stop_domain
    return CrawlAction.continue_domain
