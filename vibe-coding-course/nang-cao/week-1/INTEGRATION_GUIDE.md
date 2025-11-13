# Integration Guide: Derivatives & Multi-Platform Publisher

## Overview

This document explains how the Derivatives page integrates with the Multi-platform Publisher to create a seamless content distribution workflow.

## System Flow

```
Content Plan → Content Pack → Review → Derivatives → Multi-platform Publisher → Publish
```

## Key Integration Points

### 1. Derivatives Page (`/derivatives`)

**Purpose**: Takes approved content packs and generates platform-specific variations.

**Key Features**:
- Accepts `pack_id` parameter from Content Packs page
- Fetches associated Content Plan for context (target audience, key points)
- Generates platform-specific derivatives using AI
- Allows manual editing of each platform's content
- Displays hashtags, mentions, and character counts
- Provides "Open in Publisher" button for seamless transition

**Data Flow**:
1. Receives approved content pack
2. Generates derivatives for Twitter, LinkedIn, Facebook, Instagram, TikTok
3. Saves derivatives to database with platform-specific optimizations
4. Passes data to Multi-platform Publisher via sessionStorage

### 2. Multi-Platform Publisher (`/multi-platform-publisher`)

**Purpose**: Advanced publishing interface with analytics and scheduling.

**Key Features**:
- Receives pre-generated derivatives from Derivatives page
- Provides visual previews for all platforms
- Includes analytics dashboard
- Export options (CSV, Calendar)
- Share preview links
- Responsive preview modes (mobile/desktop)

**Integration Method**:
```javascript
// From Derivatives page
sessionStorage.setItem('derivatives_data', JSON.stringify({
  pack: selectedPack,
  plan: contentPlan,
  derivatives: platforms
}))

// In Multi-platform Publisher
const storedData = sessionStorage.getItem('derivatives_data')
const data = JSON.parse(storedData)
```

## Database Schema

### Derivatives Table
```sql
CREATE TABLE derivatives (
    id SERIAL PRIMARY KEY,
    pack_id VARCHAR(255) NOT NULL,
    content_plan_id INTEGER,
    platform VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    character_count INTEGER,
    hashtags TEXT[],
    mentions TEXT[],
    status VARCHAR(50) DEFAULT 'draft',
    scheduled_at TIMESTAMP,
    published_at TIMESTAMP
)
```

### Publishing Queue Table
```sql
CREATE TABLE publishing_queue (
    id SERIAL PRIMARY KEY,
    derivative_id INTEGER NOT NULL,
    platform VARCHAR(50) NOT NULL,
    scheduled_time TIMESTAMP NOT NULL,
    status VARCHAR(50) DEFAULT 'pending'
)
```

## API Endpoints

### Derivatives Management

- `GET /derivatives` - List all derivatives
- `GET /derivatives/pack/:packId` - Get derivatives by pack ID
- `POST /derivatives/generate` - Generate derivatives using AI
- `PUT /derivatives/:id` - Update derivative content
- `POST /derivatives/schedule` - Schedule for publishing
- `DELETE /derivatives/:id` - Delete derivative

### Request/Response Examples

**Generate Derivatives**:
```json
POST /derivatives/generate
{
  "pack_id": "pack-uuid",
  "content_plan_id": 1,
  "original_content": "Your content here",
  "platforms": [
    { "platform": "Twitter", "character_limit": 280 },
    { "platform": "LinkedIn", "character_limit": 3000 }
  ]
}
```

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "pack_id": "pack-uuid",
      "platform": "Twitter",
      "content": "Optimized tweet content...",
      "character_count": 275,
      "hashtags": ["ContentStrategy", "Marketing"],
      "mentions": ["user1"]
    }
  ]
}
```

## Platform-Specific Optimizations

### Twitter (280 chars)
- Concise messaging
- Strategic hashtag placement
- Thread capability indication
- @mentions for engagement

### LinkedIn (3000 chars)
- Professional tone
- Bullet points for readability
- Industry-specific keywords
- Call-to-action for professional engagement

### Facebook (5000 chars)
- Conversational tone
- Emoji usage for engagement
- Question prompts for comments
- Link preview optimization

### Instagram (2200 chars)
- Visual description focus
- Extensive hashtag usage (up to 30)
- Story/Reel mentions
- Location tags consideration

### TikTok (300 chars)
- Trend-focused content
- Challenge hashtags
- Short, punchy messaging
- Sound/effect references

## User Workflow

1. **Content Creation**:
   - User creates content plan
   - Generates content pack
   - Reviews and approves draft

2. **Derivative Generation**:
   - Navigate to Derivatives page with approved pack
   - Click "Generate Derivatives" to create platform variants
   - Edit individual platform content as needed
   - Review hashtags and character counts

3. **Publishing**:
   - Click "Open in Publisher" to transfer to Multi-platform Publisher
   - Review all platforms in comparison view
   - Schedule publishing times
   - Export to calendar or CSV

4. **Analytics**:
   - Monitor performance metrics
   - Track engagement across platforms
   - Optimize future content based on data

## Integration Benefits

1. **Seamless Data Transfer**: No manual copy-paste between pages
2. **Context Preservation**: Content plan data flows through entire process
3. **Platform Optimization**: AI-powered content adaptation
4. **Unified Workflow**: Single interface for multi-platform management
5. **Analytics Integration**: Performance tracking across all channels

## Error Handling

- Database connection failures: Graceful fallback with user notification
- AI generation failures: Manual editing option available
- Session storage limits: Automatic cleanup after data transfer
- Platform API limits: Rate limiting and retry logic

## Future Enhancements

1. **Direct Platform Publishing**: API integration with social platforms
2. **A/B Testing**: Multiple variants per platform
3. **Content Calendar**: Visual scheduling interface
4. **Team Collaboration**: Multi-user approval workflow
5. **Performance Predictions**: ML-based engagement forecasting

## Development Setup

1. Ensure database migrations are applied:
```bash
docker exec -i ideas_db psql -U postgres -d ideas_db < database/derivatives.sql
```

2. Start all services:
```bash
docker-compose up -d  # Database
npm run dev           # Backend (port 4000)
npm run dev           # Frontend (port 3000)
```

3. Test the flow:
   - Create and approve a content pack
   - Navigate to Derivatives with pack_id
   - Generate derivatives
   - Open in Multi-platform Publisher
   - Verify data transfer and functionality

## Troubleshooting

**Issue**: Derivatives not generating
- Check AI service configuration in backend
- Verify API keys are set in .env
- Check database connection

**Issue**: Data not transferring between pages
- Verify sessionStorage is enabled
- Check browser console for errors
- Ensure proper URL parameters

**Issue**: Platform content exceeds limits
- Review character_limit settings
- Check platform-specific truncation logic
- Verify hashtag/mention extraction

## Support

For issues or questions:
- Check backend logs: `docker logs ideas_db`
- Review frontend console for errors
- Verify all services are running properly