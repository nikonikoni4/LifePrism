from lifeprism.llm.prompts import PromptLoader,Prompts
prompt_loader = PromptLoader()
print(prompt_loader.load_prompt(Prompts.Schedule.UPDATE_MEMORY,recent_state_path="/test/recent_state.md"))