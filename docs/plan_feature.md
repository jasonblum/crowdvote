Before starting any feature planning, ALWAYS read and understand:
- docs/CHANGELOG.md - Complete development history and context
- AGENTS.md - Project guidelines, best practices, and development standards
- README.md - Project overview and current status

The user will provide a feature description. Your job is to:

1. Create a technical plan that concisely describes the feature the user wants to build.
2. Research the files and functions that need to be changed to implement the feature
3. Avoid any product manager style sections (no success criteria, timeline, migration, etc)
4. Avoid writing any actual code in the plan.
5. Include specific and verbatim details from the user's prompt to ensure the plan is accurate.
6. Plan also on writing new tests or updating old ones to ensure any changes to the code are covered with comprehensive tests.

This is strictly a technical requirements document that should:
1. Include a brief description to set context at the top
2. Point to all the relevant files and functions that need to be changed or created
3. Explain any algorithms that are used step-by-step
4. If necessary, breaks up the work into logical phases. Ideally this should be done in a way that has an initial "data layer" phase that defines the types and db changes that need to run, followed by N phases that can be done in parallel (e.g. Phase 2A - UI, Phase 2B - API). Only include phases if it's a REALLY big feature.

If the user's requirements are unclear, especially after researching the relevant files, you may ask up to 5 clarifying questions before writing the plan. If you do so, incorporate the user's answers into the plan.

Prioritize being concise and precise. Make the plan as tight as possible without losing any of the critical details from the user's requirements.

Write the plan into an docs/features/<N>_PLAN.md file with the next available feature number (starting with 0001)

After completing any significant feature or development session, update the docs/CHANGELOG.md file to document:
- What was accomplished in this session
- Key decisions made
- Files created or modified
- Next steps or remaining work
This changelog serves as a running history of the project's development for future reference.