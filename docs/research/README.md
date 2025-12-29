# TermPilot POC Migration Research

## Overview

This research package contains comprehensive analysis of the TermPilot Proof of Concept (POC) and detailed migration strategy for converting it to a production-ready application using Service-Oriented Architecture (SOA) with Dependency Injection (DI).

## Documents

### 1. **POC_ARCHITECTURE_ANALYSIS.md** (Primary Analysis)
Complete architectural breakdown of the existing POC codebase.

**Contains:**
- Executive summary and metrics
- Detailed class/function inventory (what to migrate)
- Component dependency graph
- External dependencies (no new packages needed)
- Architecture patterns already in use
- Migration strategy overview
- Testing implications
- Code quality standards

**Key Findings:**
- 2,271 LOC across 3 main files
- Well-structured with clear separation of concerns
- 4 major components: Terminal Controllers, Unified Manager, LLM Client, Chatbot
- Ready to migrate with minimal architectural changes

### 2. **MIGRATION_CHECKLIST.md** (Implementation Guide)
Step-by-step checklist for migrating POC to production.

**Contains:**
- 10 migration phases with detailed tasks
- Sub-tasks for each component
- Estimated LOC per component
- Dependency ordering (critical!)
- Definition of "done" per phase
- Risk areas and mitigations
- Success criteria

**Key Information:**
- Recommended implementation order (adapters first, then services, then API)
- Parallel task opportunities (testing during other phases)
- Risk mitigation strategies
- Estimated 3-4 weeks for one developer
- 1,800-2,000 new LOC expected

### 3. **RECOMMENDED_DI_STRUCTURE.md** (Architecture & Patterns)
Detailed dependency injection structure and implementation patterns.

**Contains:**
- DI principles being applied
- Complete container configuration
- Pattern examples for each layer (adapters, services, LLM, API)
- Singleton vs Factory decisions
- Configuration management patterns
- Testing with mocks
- Startup sequence
- Environment configuration examples

**Key Patterns:**
- Protocol-based abstraction (ITerminalAdapter, ILLMClient)
- Constructor injection for all dependencies
- Lazy instantiation via providers
- Configuration via Pydantic Settings

## Document Relationships

```
POC_ARCHITECTURE_ANALYSIS.md
├─ Current state analysis
├─ What needs to migrate
├─ How components interact
└─→ Used to create:

MIGRATION_CHECKLIST.md
├─ Step-by-step tasks
├─ Implementation order
├─ Dependency ordering
└─→ Supported by:

RECOMMENDED_DI_STRUCTURE.md
├─ How to implement DI
├─ Code examples
├─ Configuration patterns
└─→ Answers "how to build it"
```

## Quick Start: Where to Begin

1. **First:** Read **POC_ARCHITECTURE_ANALYSIS.md**
   - Understand what you're working with
   - See the class hierarchy and dependencies
   - Review existing patterns

2. **Then:** Read **MIGRATION_CHECKLIST.md**
   - See the implementation roadmap
   - Understand the correct ordering
   - See definition of done for each phase

3. **Finally:** Reference **RECOMMENDED_DI_STRUCTURE.md**
   - When implementing each component
   - To understand injection patterns
   - For code examples and best practices

## Key Insights

### Architecture Readiness
- POC is well-structured for migration
- Production `/server/` already has foundation (protocols, DI framework)
- No new dependencies needed
- Clear separation of concerns

### Component Inventory
| Layer | Files | LOC | Status |
|-------|-------|-----|--------|
| Terminal Adapters | 2 | 560+728 | Ready |
| Unified Manager | 1 | 380 | Refactor |
| LLM Client | 1 | 90 | Ready |
| Chatbot | 1 | 140 | Refactor |
| Tools & Types | 2 | ~140 | Extract |
| **Total** | **5** | **~2,271** | **Migrate** |

### Dependencies (Simple!)
```
HTTPx → OpenRouterClient
iterm2 → ITerm2Controller
libtmux → TmuxController
All wrapped by → UnifiedTerminalManager
Used by → TerminalChatbot
```

All dependencies already in `pyproject.toml`. No new packages needed!

### Implementation Complexity
- **Adapters:** Low (copy + wrap)
- **Services:** Medium (refactor logic)
- **LLM Layer:** Medium (extract + abstraction)
- **API Routes:** Low (wire services)
- **Container:** Low (configuration)
- **Tests:** Medium (comprehensive coverage)

**Overall:** Moderate complexity, well-understood patterns, clear roadmap.

## DI Structure Overview

```
Container
├─ Configuration
│   └─ Settings (from .env)
│
├─ Adapters (implement ITerminalAdapter protocol)
│   ├─ ITerm2Adapter
│   ├─ TmuxAdapter
│   └─ UnifiedAdapter (coordinates both)
│
├─ Core Services
│   ├─ TerminalService (uses UnifiedAdapter)
│   └─ AnalysisService (pure logic)
│
├─ LLM Layer
│   ├─ ILLMClient (protocol)
│   ├─ OpenRouterClient (implements protocol)
│   ├─ ToolRegistry (static definitions)
│   ├─ ToolExecutor (uses TerminalService)
│   └─ LLMEngine (routing)
│
└─ Application
    ├─ TerminalChatbot (orchestrates LLM + Terminal)
    └─ API Routes (injected services)
```

## Migration Phases Summary

| Phase | Focus | Duration | Output |
|-------|-------|----------|--------|
| 1 | Adapters | 2-3 days | 4 adapter files (~1,030 LOC) |
| 2 | Services | 1-2 days | Core services (~450 LOC) |
| 3 | LLM Layer | 2-3 days | LLM integration (~570 LOC) |
| 4 | Application | 1 day | Chatbot service (~230 LOC) |
| 5 | API Routes | 1-2 days | REST endpoints (~600 LOC) |
| 6 | DI Config | 1 day | Container wiring (~130 LOC) |
| 7 | Configuration | 1 day | Settings validation (~80 LOC) |
| 8 | Testing | 3-4 days | Test suite (~800 LOC) |
| 9 | Cleanup | 1 day | Archive & docs |
| 10 | Integration | 1-2 days | Manual testing |

## Success Criteria

- [ ] All POC logic migrated to production
- [ ] 100% of DI container wired correctly
- [ ] All endpoints working via FastAPI
- [ ] >80% test coverage
- [ ] Type hints on all public APIs
- [ ] Configuration externalized via Settings
- [ ] Async/sync properly handled (tmux thread pool)
- [ ] Documentation updated
- [ ] End-to-end flow verified

## Files to Create (During Migration)

**Adapters Layer:**
- `server/adapters/iterm2.py` - ITerm2Adapter implementation
- `server/adapters/tmux.py` - TmuxAdapter implementation
- `server/adapters/unified.py` - UnifiedAdapter orchestration
- `server/adapters/models.py` - Shared data classes

**Services Layer:**
- `server/core/terminal.py` - TerminalService (refactored)
- `server/core/analysis.py` - AnalysisService (extracted)

**LLM Layer:**
- `server/llm/client.py` - ILLMClient protocol
- `server/llm/openrouter.py` - OpenRouterClient implementation
- `server/llm/tools.py` - Tool definitions & registry
- `server/llm/executor.py` - ToolExecutor service

**Application Layer:**
- `server/services/chatbot.py` - TerminalChatbot service

**API Layer:**
- `server/api/schemas.py` - Pydantic DTOs
- `server/api/handlers.py` - Route handlers (optional)

**Updates:**
- `server/adapters/base.py` - Update protocol
- `server/config.py` - Add LLM settings
- `server/container.py` - Full DI configuration
- `server/main.py` - App initialization
- `server/api/routes.py` - API endpoints
- `server/api/dependencies.py` - FastAPI dependencies

**Testing:**
- `tests/unit/adapters/` - Adapter unit tests
- `tests/unit/services/` - Service unit tests
- `tests/unit/llm/` - LLM unit tests
- `tests/integration/` - Integration tests
- `tests/conftest.py` - Pytest configuration

**Files to Archive:**
- `scripts/poc/terminal_chatbot.py` → `docs/archive/poc/`
- `scripts/poc/iterm2_control.py` → `docs/archive/poc/`
- `scripts/poc/tmux_control.py` → `docs/archive/poc/`

## Key Decisions Made

1. **DI Framework:** Use `dependency-injector` (already in project)
2. **Protocol-Based Abstraction:** ITerminalAdapter, ILLMClient interfaces
3. **Async/Sync:** Use `asyncio.to_thread()` for tmux wrapping
4. **Singleton vs Factory:** Expensive resources = singleton, lightweight = factory
5. **Configuration:** Pydantic Settings from environment
6. **Testing:** Inject mocks, test services in isolation
7. **FastAPI Injection:** Use `Depends()` pattern for clarity

## Known Challenges & Solutions

| Challenge | Solution |
|-----------|----------|
| tmux is sync, need async | Wrap calls with `asyncio.to_thread()` |
| Session IDs are fragile | Add validation layer, consider UUIDs |
| Prompt detection heuristics | Keep POC patterns, make configurable |
| LLM API rate limits | Add retry logic, exponential backoff |
| Test iTerm2 (needs running app) | Use unit mocks, integration tests with actual iTerm2 |
| Complex tool calling loop | Extract to ToolExecutor service |
| Configuration management | Use Pydantic Settings with env vars |

## Next Steps

1. **Create migration task board** - Use MIGRATION_CHECKLIST.md as template
2. **Set up test directory structure** - Before implementing services
3. **Implement Phase 1 (Adapters)** - Foundation for everything else
4. **Then Phases 2-6 sequentially** - Build on previous layers
5. **Parallel Phase 8 (Testing)** - Write tests alongside implementation
6. **Phase 9-10** - Integration and cleanup

## Research Files

All analysis saved to: `/docs/research/`

```
docs/research/
├── README.md (this file)
├── POC_ARCHITECTURE_ANALYSIS.md
├── MIGRATION_CHECKLIST.md
└── RECOMMENDED_DI_STRUCTURE.md
```

## Questions Answered

**Q: Do we need new dependencies?**
A: No. All required packages already in `pyproject.toml`.

**Q: Can we incrementally migrate?**
A: Yes. Implement adapters first, then services, then wire into existing routes.

**Q: How do we handle async/sync mismatch with tmux?**
A: Use `asyncio.to_thread()` to wrap sync libtmux calls in async functions.

**Q: What about existing code in `/server`?**
A: Stub implementations in `/server` already follow proper patterns. We fill them in.

**Q: How do we test without actual terminals?**
A: Mock iTerm2 API and libtmux in unit tests. Use integration tests for end-to-end.

**Q: When do we delete POC code?**
A: After migration is complete and verified. Archive first, then delete.

**Q: Can tests run in parallel?**
A: Yes. Unit tests are fast and independent. Integration tests can be sequential.

## Document History

- **Created:** December 8, 2025
- **Analysis Scope:** Terminal chatbot POC (2,271 LOC across 3 files)
- **Confidence Level:** High - POC is well-structured, patterns are clear
- **Readiness:** Ready for implementation

## Related Documentation

- **POC Source:** `/scripts/poc/` (terminal_chatbot.py, iterm2_control.py, tmux_control.py)
- **Production Base:** `/server/` (adapters, core, llm, api packages)
- **Project README:** `/README.md`
- **Development Guide:** `/docs/DEVELOPMENT.md` (update during implementation)

---

## Document Map by Use Case

**"I'm new to the project. Where do I start?"**
→ Read: POC_ARCHITECTURE_ANALYSIS.md (executive summary)

**"I need to know the implementation order."**
→ Read: MIGRATION_CHECKLIST.md (phases + dependencies)

**"I'm implementing adapter layer. How do I wire DI?"**
→ Read: RECOMMENDED_DI_STRUCTURE.md (adapter examples)

**"I need to understand component dependencies."**
→ Read: POC_ARCHITECTURE_ANALYSIS.md (dependency graph)

**"I'm writing tests. What should I mock?"**
→ Read: RECOMMENDED_DI_STRUCTURE.md (testing section)

**"I need to add a new LLM provider."**
→ Read: RECOMMENDED_DI_STRUCTURE.md (LLM layer structure)

**"What's the success criteria?"**
→ Read: MIGRATION_CHECKLIST.md (definition of done) or README.md (success criteria)

---

**Status:** Research Complete ✓
**Confidence:** High ✓
**Ready for Implementation:** Yes ✓

