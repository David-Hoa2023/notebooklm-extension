# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Full-stack idea management application with AI integration, built as an educational project for the "Vibe Coding" advanced backend course (Week 1). Features Vietnamese UI and comprehensive AI provider support.

## Architecture

### Stack
- **Backend**: Fastify + TypeScript (Node.js) on port 4000
- **Frontend**: Next.js 14 + React 18 + TypeScript on port 3000  
- **Database**: PostgreSQL 15 (Docker container, port 5433)
- **AI**: Multi-provider (OpenAI, Anthropic, DeepSeek, Gemini, Kimi k2)

### Key Directories
- `idea-management-app/backend/`: Fastify API server
- `idea-management-app/frontend/`: Next.js application
- `idea-management-app/database/`: PostgreSQL setup and migrations

## Development Commands

### Start Services
```bash
# Start database
cd idea-management-app
docker-compose up -d

# Start backend (port 4000)
cd backend
npm run dev

# Start frontend (port 3000)  
cd ../frontend
npm run dev

# Or use PowerShell script (Windows)
./start-all.ps1
```

### Build & Production
```bash
# Backend
cd backend
npm run build  # Compile TypeScript
npm start      # Run production

# Frontend
cd frontend
npm run build  # Next.js production build
npm start      # Production server
```

### Testing & Linting
```bash
# Frontend linting
cd frontend
npm run lint

# Test AI integrations
cd idea-management-app
./test-ai.sh
```

## API Structure

Backend routes (`backend/src/routes/`):
- `/api/ideas/*` - CRUD for ideas
- `/api/ai/*` - AI generation endpoints  
- `/api/content-plans/*` - Content plan management
- `/health` - Health check

## AI Integration

### Backend Configuration
Configured in `backend/src/services/aiService.ts`:
- Auto-retry with exponential backoff (3 attempts)
- Provider fallback on failure
- Configurable temperature and token limits
- API keys from environment variables

### Frontend LLM Settings
Accessible via Settings page (`frontend/src/app/settings/page.tsx`):
- **LLM Provider Switcher**: Complete UI for managing AI providers
- **Supported Providers**: OpenAI, Anthropic, DeepSeek, Gemini, Kimi k2
- **API Key Management**: Secure local storage with show/hide functionality
- **Model Selection**: Provider-specific model options with cost/performance info
- **Connection Testing**: Validate API keys before use
- **Task-based Defaults**: Set different providers for different task types
- **Auto-persistence**: Settings saved to browser localStorage

#### Provider Details:
- **OpenAI**: GPT-4o, GPT-3.5 Turbo
- **Anthropic**: Claude 3 Opus, Claude 3 Sonnet  
- **DeepSeek**: Chat, Coder models
- **Gemini**: 1.5 Pro
- **Kimi k2**: Moonshot v1 (8K, 32K, 128K context)

## Database Schema

Two main tables (`database/init.sql`):
- `ideas`: id, title, description, status, tags, metadata
- `content_plans`: id, idea_id, plan_data, created_at

## Frontend Components

- Page structure: `frontend/src/app/` (App Router)
- UI components: `frontend/src/components/ui/` (shadcn/ui pattern)
- Layout: `frontend/src/components/layout/`
- Features: Tabbed interface, dark mode, markdown editor

### Key UI Components:
- **LLM Provider Switcher** (`frontend/src/components/ui/llm-provider-switcher.tsx`): Complete AI provider management
- **Settings Page** (`frontend/src/app/settings/page.tsx`): User preferences and LLM configuration
- **Navigation** (`apps/web/app/components/Navigation.tsx`): Top navigation with Settings access

## Environment Variables

Required in `.env`:
```
POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
OPENAI_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY, DEEPSEEK_API_KEY
```

**Note**: API keys can now also be configured via the frontend Settings page, which stores them securely in browser localStorage. This provides an alternative to environment variables for development and testing.

## Notes

- Vietnamese language UI and documentation
- No unit test framework - use manual testing
- CORS enabled for development
- Docker required for database

# Claude Development Guide (TDD Workflow)

## Nguyên tắc chung
- Luôn viết **test trước** khi thêm tính năng mới.
- Mỗi thay đổi phải đi kèm ít nhất một test mô tả hành vi mong muốn.
- Chạy `cargo test` và `cargo check` liên tục để đảm bảo tính đúng đắn.

## Quy trình làm việc
1. **Research (Nghiên cứu)**
   - Xác định chức năng cần thêm hoặc bug cần sửa.
   - Viết mô tả hành vi mong muốn bằng ngôn ngữ tự nhiên.

2. **Plan (Lập kế hoạch)**
   - Viết test case trong thư mục `tests/` hoặc module `mod tests`.
   - Test phải mô tả rõ input và output mong đợi.
   - Ví dụ:
     ```rust
     #[test]
     fn it_adds_two_numbers() {
         assert_eq!(add(2, 3), 5);
     }
     ```

3. **Implement (Thực hiện)**
   - Viết code tối thiểu để pass test.
   - Không viết thêm logic ngoài phạm vi test.
   - Chạy `cargo test` sau mỗi thay đổi.

## Quy tắc kiểm thử
- **Unit test** cho từng hàm nhỏ.
- **Integration test** cho các module lớn.
- Luôn chạy `cargo check` trước commit để đảm bảo không có lỗi biên dịch.

## Ví dụ minh họa
- Thêm tính năng WASM:
  - Viết test kiểm tra rằng module WASM có thể compile và chạy một hàm đơn giản.
  - Sau đó mới viết code để pass test này.