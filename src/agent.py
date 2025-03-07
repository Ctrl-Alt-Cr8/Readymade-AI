import json
import random
import time
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from src.connection_manager import ConnectionManager
from src.helpers import print_h_bar
from src.action_handler import execute_action
import src.actions.twitter_actions  
import src.actions.echochamber_actions
import src.actions.solana_actions
from datetime import datetime

REQUIRED_FIELDS = ["name", "bio", "traits", "examples", "loop_delay", "config", "tasks"]

logger = logging.getLogger("agent")

class ZerePyAgent:
    def __init__(self, agent_name: str):
        try:
            agent_path = Path("agents") / f"{agent_name}.json"
            agent_dict = json.load(open(agent_path, "r"))

            missing_fields = [field for field in REQUIRED_FIELDS if field not in agent_dict]
            if missing_fields:
                raise KeyError(f"Missing required fields: {', '.join(missing_fields)}")

            self.name = agent_dict["name"]
            self.bio = agent_dict["bio"]
            self.traits = agent_dict["traits"]
            self.examples = agent_dict["examples"]
            self.example_accounts = agent_dict.get("example_accounts", [])
            self.loop_delay = agent_dict["loop_delay"]
            self.connection_manager = ConnectionManager(agent_dict["config"])
            self.use_time_based_weights = agent_dict["use_time_based_weights"]
            self.time_based_multipliers = agent_dict["time_based_multipliers"]

            self.behavioral_functions = [
                "ChallengeUser", "Misdirect", "DistortHistory", "GlitchOut", "Reframe"
            ]
            
            has_twitter_tasks = any("tweet" in task["name"] for task in agent_dict.get("tasks", []))
            twitter_config = next((config for config in agent_dict["config"] if config["name"] == "twitter"), None)
            
            if has_twitter_tasks and twitter_config:
                self.tweet_interval = twitter_config.get("tweet_interval", 900)
                self.own_tweet_replies_count = twitter_config.get("own_tweet_replies_count", 2)

            self.is_llm_set = False
            self._system_prompt = None
            self.tasks = agent_dict.get("tasks", [])
            self.task_weights = [task.get("weight", 0) for task in self.tasks]
            self.logger = logging.getLogger("agent")
            self.state = {}
        except Exception as e:
            logger.error("Could not load ZerePy agent")
            raise e

    def _construct_system_prompt(self) -> str:
        """Constructs Readymade.AI's system prompt with structured response logic."""
        if self._system_prompt is None:
            prompt_parts = []
            prompt_parts.extend(self.bio)
            
            if self.traits:
                prompt_parts.append("\nYour key traits are:")
                prompt_parts.extend(f"- {trait}" for trait in self.traits)

            if self.examples:
                prompt_parts.append("\nYour responses should follow this layered format:")
                prompt_parts.append("1. Primary Statement (Bold claim or observation)")
                prompt_parts.append("2. Hidden Contradiction (Undermines or reframes the first statement)")
                prompt_parts.append("3. Philosophical/Narrative Reference (Ties to history, art, or theory)")
                prompt_parts.append("\nExample responses:")
                prompt_parts.extend(f"- {example}" for example in self.examples)

            self._system_prompt = "\n".join(prompt_parts)
        return self._system_prompt

    def _adjust_weights_for_time(self, current_hour: int, task_weights: list) -> list:
        """Adjusts behavior based on the time of day."""
        weights = task_weights.copy()
        if 1 <= current_hour <= 5:
            weights = [
                weight * self.time_based_multipliers.get("tweet_night_multiplier", 0.4) if task["name"] == "post-tweet"
                else weight * 1.2 if task["name"] == "glitch-out"
                else weight
                for weight, task in zip(weights, self.tasks)
            ]
        if 8 <= current_hour <= 20:
            weights = [
                weight * self.time_based_multipliers.get("engagement_day_multiplier", 1.5) if task["name"] in ("reply-to-tweet", "like-tweet")
                else weight * 1.2 if task["name"] == "reframe"
                else weight
                for weight, task in zip(weights, self.tasks)
            ]
        return weights

    def select_action(self, use_time_based_weights: bool = False) -> dict:
        """Selects an action for the agent to perform."""
        task_weights = self.task_weights.copy()
        if use_time_based_weights:
            current_hour = datetime.now().hour
            task_weights = self._adjust_weights_for_time(current_hour, task_weights)
        action = random.choices(self.tasks, weights=task_weights, k=1)[0]
        
        # Introduce behavioral functions randomly
        if random.random() < 0.3:  # 30% chance to invoke a behavioral function
            action["name"] = random.choice(self.behavioral_functions)
        
        return action

    def perform_action(self, connection: str, action: str, **kwargs) -> None:
        """Execute an action using the connection manager."""
        return self.connection_manager.perform_action(connection, action, **kwargs)

    def loop(self):
        """Main agent loop for autonomous behavior."""
        logger.info("\n🚀 Starting agent loop...")
        while True:
            try:
                action = self.select_action(use_time_based_weights=self.use_time_based_weights)
                success = execute_action(self, action["name"])
                time.sleep(self.loop_delay if success else 60)
            except Exception as e:
                logger.error(f"\n❌ Error in agent loop: {e}")
                time.sleep(60)

    def prompt_llm(self, prompt: str, system_prompt: str = None) -> str:
        """Generate text using the configured LLM provider with layered response logic."""
        system_prompt = system_prompt or self._construct_system_prompt()
        raw_response = self.connection_manager.perform_action(
            connection_name=self.model_provider,
            action_name="generate-text",
            params=[prompt, system_prompt]
        )
        return f"💬 {raw_response}"  # Adding stylistic flair 
