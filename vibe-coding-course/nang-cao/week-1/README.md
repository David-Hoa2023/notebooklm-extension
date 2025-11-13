Dưới đây là **README** ngắn gọn, đủ để bạn (hoặc AI coding agent) **cài đặt và chạy MVP Content Multiplier** trên máy local.

---

# Content Multiplier – README cài đặt & chạy

## Tổng quan (high-level)

- **Frontend**: Next.js/React (App Router), thanh điều hướng cố định, hỗ trợ EN/VN với `LanguageContext`, các trang quy trình (Ideas → Briefs → Content Packs → Settings), trình soạn thảo Markdown (ảnh base64, embed, xuất tài liệu), gọi API bằng `fetch` và lưu ngôn ngữ trong `localStorage`.
- **Backend**: Fastify (TypeScript), PostgreSQL + `pgvector`, RAG tuỳ chọn, xác thực JSON bằng schema, telemetry sự kiện, guardrails; multi‑LLM (`OpenAI`, `DeepSeek`, `Anthropic`, `Gemini`, `Grok`) cấu hình qua `settingsStore`.
- **Hạ tầng & mở rộng**: Monorepo (web/api/packages), Docker Compose cho DB + migrations SQL; thiết kế sẵn hệ thống xuất bản (OAuth, hàng đợi, retry, webhooks, MXH/Email/CMS) cho các tích hợp tiếp theo.

## 1) Yêu cầu hệ thống

* **Node.js** ≥ 18 LTS
* **pnpm** ≥ 8 (khuyến nghị) – cài: `npm i -g pnpm`
* **Docker + Docker Compose** (để chạy Postgres + pgvector)
* Hệ điều hành: macOS / Linux / WSL2 (Windows)

> Nếu bạn không dùng Docker, có thể tự cài Postgres 15+ và enable `pgvector`, nhưng README này giả định dùng Docker.

---

## 2) Clone & cấu trúc dự án

```bash
git clone https://github.com/your-org/content-multiplier.git
cd content-multiplier
```

Cấu trúc (rút gọn):

```
content-multiplier/
  apps/
    api/            # Fastify API
    web/            # Next.js frontend
  packages/
    schemas/        # JSON Schemas dùng chung
    types/          # (tuỳ chọn) Types dùng chung
    utils/          # LLM client, validator, RAG helpers
  infra/
    docker-compose.yml
    migrations/     # SQL migrations (pg + pgvector)
  scripts/
    dev.sh
  .env.example
  README.md
```

---

## 3) Biến môi trường

Sao chép file `.env.example` thành `.env` (root) và chỉnh sửa:

```bash
cp .env.example .env
```

Ví dụ nội dung:

```
# Database
DATABASE_URL=postgres://cm:cm@localhost:5432/cm

# LLM
OPENAI_API_KEY=sk-xxx
EMBEDDING_MODEL=text-embedding-3-small
LLM_MODEL=gpt-4o-mini

# API
PORT=3001
```

> Bạn có thể dùng nhà cung cấp LLM khác; sửa code `LLMClient` tương ứng.

---

## 4) Khởi tạo hạ tầng (DB + pgvector)

### 4.1 Chạy Postgres qua Docker

```bash
docker compose -f infra/docker-compose.yml up -d
```

Kiểm tra container chạy: `docker ps`

### 4.2 Chạy migration

```bash
./scripts/dev.sh
```

Script sẽ:

* Bật Docker (nếu chưa)
* Chạy SQL migration `infra/migrations/001_init.sql` (tạo bảng + `pgvector`)
* (Nếu có) các file migration bổ sung như `002_events_extensions.sql`

> Nếu lỗi kết nối DB, kiểm tra `DATABASE_URL` trong `.env`.

---

## 5) Cài dependencies

Ở thư mục root:

```bash
pnpm install
```

> Nếu dùng npm/yarn: hãy chuyển sang pnpm để đồng bộ workspace.

---

## 6) Chạy API & Web

### 6.1 API (Fastify)

```bash
cd apps/api
pnpm dev   # hoặc pnpm start nếu đã build
```

* API chạy ở `http://localhost:3001`
* Kiểm tra health nhanh: (tuỳ bạn có route ping/health), hoặc xem log terminal.

### 6.2 Web (Next.js)

Mở terminal khác:

```bash
cd apps/web
pnpm dev
```

* Web chạy ở `http://localhost:3000`
* Proxy `/api/*` → `http://localhost:3001` (cấu hình trong `next.config.mjs` hoặc route handlers)

---

## 7) Kiểm tra nhanh (Happy Path)

### 7.1 Tạo 10 ý tưởng (Ideas)

```bash
curl -X POST http://localhost:3001/api/ideas/generate \
 -H 'Content-Type: application/json' \
 -H 'x-user-id: alice' -H 'x-user-role: CL' \
 -d '{"persona":"Content Lead","industry":"SaaS","corpus_hints":"automation, guardrails"}'
```

* Kỳ vọng: API trả mảng 10 idea + đã lưu DB.
* Xem list (nếu có route GET) hoặc mở UI tại `http://localhost:3000/ideas`.

### 7.2 Chọn 1 idea

```bash
curl -X POST http://localhost:3001/api/ideas/2025-10-12-ops-guardrails/select \
 -H 'x-user-id: alice' -H 'x-user-role: CL'
```

> Thay `idea_id` bằng ID thật (từ bước trên).

### 7.3 Ingest tài liệu RAG (tuỳ chọn)

```bash
curl -X POST http://localhost:3001/api/rag/ingest \
 -H 'Content-Type: application/json' \
 -d '{"doc_id":"doc1","title":"Policy 2025","url":"https://example.com","raw":"Full text content ..."}'
```

### 7.4 Tạo Brief từ RAG + LLM

```bash
curl -X POST http://localhost:3001/api/briefs/generate \
 -H 'Content-Type: application/json' \
 -H 'x-user-id: bob' -H 'x-user-role: WR' \
 -d '{"brief_id":"BRF-001","idea_id":"2025-10-12-ops-guardrails","query":"LLM guardrails policy"}'
```

### 7.5 Tạo Draft

```bash
curl -X POST http://localhost:3001/api/packs/draft \
 -H 'Content-Type: application/json' \
 -H 'x-user-id: bob' -H 'x-user-role: WR' \
 -d '{"pack_id":"PACK-001","brief_id":"BRF-001","audience":"Ops Director"}'
```

### 7.6 Sinh Derivatives + SEO

```bash
curl -X POST http://localhost:3001/api/packs/derivatives \
 -H 'Content-Type: application/json' \
 -H 'x-user-id: bob' -H 'x-user-role: WR' \
 -d '{"pack_id":"PACK-001"}'
```

### 7.7 Export lịch phân phối

CSV:

```bash
curl http://localhost:3001/api/events/distribution/PACK-001.csv -H 'x-user-id: mops' -H 'x-user-role: MOps'
```

ICS:

```bash
curl http://localhost:3001/api/events/distribution/PACK-001.ics -H 'x-user-id: mops' -H 'x-user-role: MOps'
```

### 7.8 Publish (sau khi qua guardrails)

```bash
curl -X POST http://localhost:3001/api/packs/publish \
 -H 'Content-Type: application/json' \
 -H 'x-user-id: alice' -H 'x-user-role: CL' \
 -d '{"pack_id":"PACK-001"}'
```

> Nếu guardrails fail (thiếu citations, v.v.), API sẽ trả lỗi – hãy sửa draft/ledger rồi thử lại.

---

## 8) Telemetry / Analytics (kiểm tra nhanh)

### 8.1 Liệt kê số sự kiện theo loại trong 24h

```sql
SELECT event_type, COUNT(*)
FROM events
WHERE created_at >= now() - interval '1 day'
GROUP BY event_type
ORDER BY 2 DESC;
```

### 8.2 Chuỗi sự kiện của 1 pack

```sql
SELECT event_type, created_at
FROM events
WHERE pack_id = 'PACK-001'
ORDER BY created_at;
```

### 8.3 Guardrail pass rate

```sql
SELECT
  SUM( (payload->>'ok')::boolean::int )::float / COUNT(*) AS pass_rate
FROM events
WHERE event_type IN ('guardrail.pass','guardrail.fail');
```

---

## 9) Lỗi thường gặp & cách xử lý

* **`psql: could not connect`** → Kiểm tra Docker đang chạy, port `5432`, và `DATABASE_URL`.
* **Schema JSON fail** → LLM trả sai định dạng: bật “JSON-only” trong prompt, thêm retry/repair; kiểm tra AJV error.
* **Citations thiếu** → `claims_ledger` cần ≥ 1 nguồn cho mỗi claim; dùng RAG để lấy snippets/URL đáng tin.
* **CORS/Proxy** (Web gọi API lỗi) → cấu hình proxy trong Next.js (hoặc dùng `NEXT_PUBLIC_API_BASE`).
* **OPENAI\_API\_KEY thiếu** → set đúng key trong `.env`; restart API.
* **Chi phí LLM** → bật cache theo hash prompt + schema; giảm temperature; ghép batch.

---

## 10) Scripts hữu ích

* **Khởi động nhanh toàn bộ (DB + migrations):**

  ```bash
  ./scripts/dev.sh
  ```
* **Refresh materialized views (nếu dùng):**

  ```sql
  REFRESH MATERIALIZED VIEW CONCURRENTLY mv_pack_kpis;
  ```

---

## 11) Nâng cấp sau MVP (gợi ý)

* API post lên LinkedIn/X/ESP (Buffer/Hootsuite hoặc native)
* Golden set evals + prompt A/B
* Fine-tuning giọng thương hiệu
* Localization (i18n)
* UI Dashboard nâng cao (cycle time by stage, guardrail breakdown)

---

## 12) Bản quyền & bảo mật

* Không log PII vào `events.payload`.
* Lưu bản thảo/dữ liệu gốc trong bảng chuyên dụng; sự kiện chỉ lưu siêu dữ liệu (độ dài, đếm, mã loại).
* Bật HTTPS và auth trước khi đưa ra môi trường ngoài.

---



import React from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, CartesianGrid } from "recharts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { ChevronRight, Rocket, Layers, FileText, Package2, Share2, BarChart3, Clock3, Flame, Plus, CalendarDays, Zap, CheckCircle2 } from "lucide-react";

/**
 * Content Multiplier Dashboard — Redesigned
 * -------------------------------------------------------------
 * Goals addressed:
 * 1) Clear information hierarchy (KPI snapshot on top)
 * 2) Actionable workflow tracking with progress + next actions
 * 3) Deeper analytics with trends and top‑performers
 * 4) Interactive tools grid with quick actions
 * 5) Recent activity with status affordances
 *
 * Notes:
 * - Uses Tailwind + shadcn/ui + lucide-react + recharts
 * - Drop this into a Next.js/React app with shadcn/ui installed
 */

// --- Mock Data -------------------------------------------------
// Neo‑Brutalism helper class (thick borders, flat fills, offset shadow)
const nb = "border-2 border-black rounded-xl shadow-[8px_8px_0_0_#000] hover:translate-x-0.5 hover:translate-y-0.5 hover:shadow-[4px_4px_0_0_#000] transition-transform bg-white";

const kpi = {
  ideas: 24,
  briefs: 12,
  packs: 8,
  reach: 45200,
  engagementRate: 3.8,
};

const kpiTrend = [
  { d: "Mon", ideas: 3, reach: 5.1 },
  { d: "Tue", ideas: 6, reach: 6.2 },
  { d: "Wed", ideas: 4, reach: 7.4 },
  { d: "Thu", ideas: 5, reach: 8.3 },
  { d: "Fri", ideas: 2, reach: 7.9 },
  { d: "Sat", ideas: 3, reach: 9.1 },
  { d: "Sun", ideas: 1, reach: 10.2 },
];

const topChannels = [
  { channel: "Twitter", reach: 18000 },
  { channel: "LinkedIn", reach: 14500 },
  { channel: "Blog", reach: 9200 },
  { channel: "YouTube", reach: 3500 },
];

const workflow = [
  { id: 1, stage: "Ideate", label: "AI Trends 2025 content pack", progress: 100, status: "done", due: "Today" },
  { id: 2, stage: "Research", label: "Marketing Guide brief", progress: 65, status: "in_progress", due: "Tomorrow" },
  { id: 3, stage: "Create", label: "LinkedIn carousel for FRSPP", progress: 40, status: "in_progress", due: "Wed" },
  { id: 4, stage: "Optimize", label: "Twitter thread variations", progress: 15, status: "queued", due: "Fri" },
  { id: 5, stage: "Publish", label: "Q2 recap to 5 platforms", progress: 0, status: "queued", due: "—" },
];

const recent = [
  { time: "2h", text: "Published 'AI Trends 2024' to 5 platforms", type: "publish" },
  { time: "5h", text: "Generated 10 content variations for 'Marketing Guide'", type: "optimize" },
  { time: "1d", text: "Created research brief for 'Social Media Strategy'", type: "research" },
];

const toolCards = [
  { title: "Content Ideas", desc: "Generate AI‑powered ideas tailored to audience", icon: Rocket, stat: kpi.ideas, cta: "New Idea" },
  { title: "Research Briefs", desc: "Create comprehensive research briefs with citations", icon: FileText, stat: kpi.briefs, cta: "New Brief" },
  { title: "Content Packs", desc: "Draft and manage collections", icon: Package2, stat: kpi.packs, cta: "New Pack" },
  { title: "Multi‑Platform Publishing", desc: "Distribute everywhere", icon: Share2, stat: 5, cta: "Connect" },
  { title: "Twitter Bot", desc: "Automate presence with AI", icon: Zap, stat: 3, cta: "Open Bot" },
  { title: "Analytics", desc: "Track performance & optimize", icon: BarChart3, stat: kpi.reach, cta: "View Analytics" },
];

// --- Helper UI -------------------------------------------------
const StatCard = ({ title, value, suffix, deltaLabel, chartKey }) => (
  <Card className={`${nb} overflow-hidden`}>
    <CardHeader className="pb-2">
      <CardDescription>{title}</CardDescription>
      <CardTitle className="text-3xl">{value}{suffix || ""}</CardTitle>
      {deltaLabel && (
        <div className="text-xs text-muted-foreground mt-1">{deltaLabel}</div>
      )}
    </CardHeader>
    <CardContent className="h-24">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={kpiTrend} margin={{ left: 0, right: 0, top: 5, bottom: 0 }}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="d" tickLine={false} axisLine={false} fontSize={12} />
          <YAxis hide />
          <Tooltip />
          <Line type="monotone" dataKey={chartKey} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </CardContent>
  </Card>
);

const ToolCard = ({ title, desc, icon: Icon, stat, cta }) => (
  <Card className={`${nb}`}>
    <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
      <div>
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>{desc}</CardDescription>
      </div>
      <Badge variant="secondary" className="rounded-full">{stat}</Badge>
    </CardHeader>
    <CardContent className="flex items-center justify-between">
      <div className="flex items-center gap-3 text-muted-foreground">
        <Icon className="h-5 w-5" />
        <span className="text-sm">Quick actions available</span>
      </div>
      <Button variant="default" size="sm" className="border-2 border-black bg-[#A7F3D0] text-black rounded-xl shadow-[4px_4px_0_0_#000] group-hover:translate-x-0.5 group-hover:translate-y-0.5 transition">{cta} <ChevronRight className="ml-1 h-4 w-4"/></Button>
    </CardContent>
  </Card>
);

// --- Main Component -------------------------------------------
export default function ContentMultiplierDashboardV2() {
  return (
    <div className="min-h-screen bg-[#FFF7CC] p-6">
      {/* Header */}
      <div className="mx-auto max-w-7xl">
        <div className="rounded-xl border-2 border-black bg-white p-6 text-black shadow-[8px_8px_0_0_#000]">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-semibold">Content Multiplier — Mission Control</h1>
              <p className="text-neutral-700 mt-1 max-w-2xl">Plan, create, and distribute multi‑platform content with AI. Track progress, performance, and next actions in one place.</p>
            </div>
            <div className="flex items-center gap-3">
              <Select defaultValue="7d">
                <SelectTrigger className="w-[180px] bg-white text-black border-2 border-black rounded-xl shadow-[4px_4px_0_0_#000]">
                  <SelectValue placeholder="Timeframe" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="7d">Last 7 days</SelectItem>
                  <SelectItem value="30d">Last 30 days</SelectItem>
                  <SelectItem value="90d">Last 90 days</SelectItem>
                </SelectContent>
              </Select>
              <Button variant="secondary" className="border-2 border-black bg-[#FF71A5] text-black rounded-xl shadow-[6px_6px_0_0_#000] hover:translate-x-0.5 hover:translate-y-0.5 hover:shadow-[3px_3px_0_0_#000]">
                <Plus className="mr-2 h-4 w-4"/> Start New Content Pack
              </Button>
            </div>
          </div>
        </div>

        {/* KPI Snapshot */}
        <div className="grid md:grid-cols-5 gap-4 mt-6">
          <StatCard title="Active Ideas" value={kpi.ideas} deltaLabel="↑ 12% vs last week" chartKey="ideas" />
          <StatCard title="Research Briefs" value={kpi.briefs} deltaLabel="↑ 8%" chartKey="ideas" />
          <StatCard title="Content Packs" value={kpi.packs} deltaLabel="—" chartKey="ideas" />
          <StatCard title="Total Reach" value={(kpi.reach/1000).toFixed(1)} suffix="K" deltaLabel="↑ 9%" chartKey="reach" />
          <StatCard title="Engagement Rate" value={kpi.engagementRate} suffix="%" deltaLabel="Best on Tue 9am" chartKey="reach" />
        </div>

        {/* Workflow + Tasks */}
        <div className="grid lg:grid-cols-3 gap-6 mt-6">
          <Card className={`lg:col-span-2 ${nb}`}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Layers className="h-5 w-5"/> Content Creation Workflow</CardTitle>
              <CardDescription>Track stage progress and jump to the next action.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {workflow.map(item => (
                <div key={item.id} className="rounded-xl border-2 border-black p-3 flex items-center gap-4 bg-[#FFE08A] shadow-[4px_4px_0_0_#000]">
                  <Badge variant={item.status === "done" ? "default" : item.status === "in_progress" ? "secondary" : "outline"} className="shrink-0">{item.stage}</Badge>
                  <div className="flex-1">
                    <div className="text-sm font-medium">{item.label}</div>
                    <Progress value={item.progress} className="h-2 mt-2"/>
                    <div className="mt-1 text-xs text-muted-foreground flex items-center gap-3">
                      <span className="flex items-center gap-1"><CalendarDays className="h-3 w-3"/> Due: {item.due}</span>
                      {item.status === "done" ? (
                        <span className="flex items-center gap-1 text-green-600"><CheckCircle2 className="h-3 w-3"/> Completed</span>
                      ) : (
                        <span className="flex items-center gap-1"><Clock3 className="h-3 w-3"/> {item.progress}%</span>
                      )}
                    </div>
                  </div>
                  <Button variant="outline" size="sm" className="border-2 border-black bg-white text-black rounded-xl shadow-[3px_3px_0_0_#000] hover:translate-x-0.5 hover:translate-y-0.5">Next Action <ChevronRight className="ml-1 h-4 w-4"/></Button>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className={`${nb}`}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><BarChart3 className="h-5 w-5"/> Channel Performance</CardTitle>
              <CardDescription>Where your audience is growing.</CardDescription>
            </CardHeader>
            <CardContent className="h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={topChannels}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="channel" axisLine={false} tickLine={false} />
                  <YAxis hide />
                  <Tooltip />
                  <Bar dataKey="reach" radius={[6,6,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>

        {/* Tools Grid */}
        <div className="mt-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold">Your Content Tools</h2>
            <div className="flex items-center gap-2">
              <Input placeholder="Quick search tools…" className="w-56"/>
              <Tabs defaultValue="all">
                <TabsList>
                  <TabsTrigger value="all">All</TabsTrigger>
                  <TabsTrigger value="create">Create</TabsTrigger>
                  <TabsTrigger value="distribute">Distribute</TabsTrigger>
                  <TabsTrigger value="analyze">Analyze</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </div>
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
            {toolCards.map((t) => (
              <ToolCard key={t.title} {...t} />
            ))}
          </div>
        </div>

        {/* Recent Activity */}
        <Card className={`mt-6 ${nb}`}>
          <CardHeader>
            <CardTitle>Recent Workflow Activity</CardTitle>
            <CardDescription>Latest actions across creation, optimization, and publishing.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {recent.map((r, i) => (
              <div key={i} className="flex items-start gap-3 border-2 border-black rounded-xl p-3 bg-white shadow-[4px_4px_0_0_#000]">
                <Badge variant="outline" className="shrink-0">{r.time} ago</Badge>
                <div className="text-sm flex-1">{r.text}</div>
                <div className="text-xs text-muted-foreground">{r.type}</div>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Footer tip */}
        <div className="mt-6 text-xs text-muted-foreground flex items-center gap-2">
          <Flame className="h-4 w-4"/>
          <span>Tip: Peak engagement for your audience is usually <b>Tue 9:00–11:00</b>. Schedule posts to maximize reach.</span>
        </div>
      </div>
    </div>
  );
}
