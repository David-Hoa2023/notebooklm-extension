To build a self-evolving agent that continuously updates its memory and tools during test-time deployment, you must integrate the conceptual dimensions from Gao et al. with the concrete architectural pipelines of the **MemProbe** system and the **Evolutionary Coding Agent Roadmap**. 

Here is the blueprint for engineering this exact evolutionary loop:

### Phase 1: The "What" (Evolving Memory & Tools)
To evolve without updating static neural network weights, the agent needs a persistent, highly structured non-parametric memory system. 
*   **Evolving Memory (The 3-Compartment Architecture):** Set up a Vector Database separated by metadata into three distinct namespaces so the agent can store different levels of abstraction without confusion.
    *   **Interaction Memory:** Stores the raw trajectory, terminal commands, and exact code written.
    *   **Insight Memory:** Stores concise summaries, patterns, and lessons learned.
    *   **Skill Memory:** Stores high-level, generalized procedures. 
*   **Evolving Tools (Skill Synthesis):** The agent must dynamically create its own tools. Whenever the agent successfully completes a task, use a module-ization pipeline to abstract the successful code into a reusable function with a clear name, signature, and docstring. Once this function passes an automated unit test inside an isolated sandbox, it is saved into the "Skill" memory bank, becoming a new, retrievable tool for future tasks.

### Phase 2: The "When" (Continuous Test-Time Deployment)
The evolution must happen entirely during the agent's inference phase (test-time) using a continuous **retrieve–solve–consolidate loop**.
*   **Intra/Inter-Test-Time Retrieval:** Before acting on a new environment prompt, the agent queries its memory database. To avoid being overwhelmed by past data, the agent only retrieves the top-$k$ (e.g., top-2) most relevant memories, combining semantic similarity with factors like importance and recency.
*   **Online Accumulation:** After solving the task, the agent immediately consolidates its experience and writes it back into the persistent database, making the updated memory state instantly available for the very next task it faces.

### Phase 3: The "How" (Textual Feedback & Rewards)
Because real-world open-ended environments lack perfect human guidance, the agent must autonomously extract its own rewards and textual feedback using a **Validation Gate**.
*   **Extracting Rewards (Deterministic Checkers):** Use an automated syntactic checker or a secure execution sandbox to evaluate if the agent's generated action or code actually runs. If the code executes successfully (a positive reward), the agent is permitted to write the full experience synchronously into all three memory compartments (Interaction, Insight, and Skill).
*   **Extracting Textual Feedback (Failure Modes):** If the execution fails or crashes (a negative reward), the pipeline calls upon an LLM Judge. The agent is forced to analyze why it failed, explicitly extracting the **"Failure Mode"** as textual feedback. Crucially, the system blocks the raw failed code from entering the Interaction memory to prevent the agent from replaying bad code, but saves the textual feedback into the Insight memory as a warning to help the agent avoid repeating the mistake.

### Phase 4: Lifecycle Maintenance (Sustaining the Loop)
To ensure the agent scales toward Artificial Super Intelligence (ASI) without its memory degrading into cognitive interference, you must implement lifecycle management. 
*   **Deduplication and Conflict Resolution:** Before writing new insights, the loop must check for semantic similarity to merge redundant experiences and resolve contradictory textual feedback. 
*   **Forgetting / Eviction:** Apply a decay mechanism to evict outdated or rarely used insights from the Vector DB, ensuring the agent's context remains sharp as its understanding of the environment evolves.