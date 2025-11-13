# Platform Integration Architecture

## Overview

This document outlines the design for integrating multiple publishing platforms (Email/MailChimp, WordPress, and existing social media) with proper authentication, settings management, and content adaptation.

## Architecture Components

### 1. Platform Registry System
```
platforms/
├── base/
│   ├── BasePlatform.ts          # Abstract base class
│   ├── PlatformConfig.ts        # Configuration interface
│   └── AuthTypes.ts             # Authentication types
├── social/
│   ├── TwitterPlatform.ts       # Twitter integration
│   ├── LinkedInPlatform.ts      # LinkedIn integration
│   ├── FacebookPlatform.ts      # Facebook integration
│   ├── InstagramPlatform.ts     # Instagram integration
│   └── TikTokPlatform.ts        # TikTok integration
├── email/
│   ├── MailChimpPlatform.ts     # MailChimp integration
│   ├── ConstantContactPlatform.ts
│   └── SendGridPlatform.ts
├── cms/
│   ├── WordPressPlatform.ts     # WordPress integration
│   ├── MediumPlatform.ts        # Medium integration
│   └── Ghost Platform.ts       # Ghost CMS integration
└── registry.ts                 # Platform factory
```

### 2. Database Schema Enhancement

#### Platform Configurations Table
```sql
CREATE TABLE platform_configurations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER, -- For multi-user support
    platform_type VARCHAR(50) NOT NULL, -- 'twitter', 'mailchimp', 'wordpress'
    platform_name VARCHAR(100), -- User-defined name "Marketing WordPress"
    configuration JSONB NOT NULL, -- Platform-specific config
    credentials JSONB, -- Encrypted authentication data
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Enhanced Derivatives Table
```sql
ALTER TABLE derivatives ADD COLUMN platform_config_id INTEGER;
ALTER TABLE derivatives ADD COLUMN publication_metadata JSONB;
ALTER TABLE derivatives ADD COLUMN publication_url TEXT;
ALTER TABLE derivatives ADD COLUMN platform_response JSONB;

-- Add foreign key
ALTER TABLE derivatives 
ADD CONSTRAINT fk_platform_config 
FOREIGN KEY (platform_config_id) 
REFERENCES platform_configurations(id);
```

### 3. Platform-Specific Configurations

#### Email Platforms (MailChimp, Constant Contact)
```typescript
interface EmailPlatformConfig {
  type: 'mailchimp' | 'constant_contact' | 'sendgrid'
  apiKey: string
  listId?: string
  templateId?: string
  fromName: string
  fromEmail: string
  replyTo: string
  trackOpens: boolean
  trackClicks: boolean
  segmentTags?: string[]
  customFields?: Record<string, any>
}
```

#### WordPress Configuration
```typescript
interface WordPressPlatformConfig {
  type: 'wordpress'
  siteUrl: string
  authType: 'basic' | 'oauth' | 'application_password'
  credentials: {
    username?: string
    password?: string
    applicationPassword?: string
    clientId?: string
    clientSecret?: string
  }
  defaultCategory?: string
  defaultTags?: string[]
  defaultStatus: 'draft' | 'pending' | 'private' | 'publish'
  featuredImageUrl?: string
  customFields?: Record<string, any>
}
```

#### Social Media Configuration
```typescript
interface SocialPlatformConfig {
  type: 'twitter' | 'linkedin' | 'facebook' | 'instagram' | 'tiktok'
  credentials: {
    accessToken: string
    refreshToken?: string
    apiKey?: string
    apiSecret?: string
    accountId?: string
  }
  defaultHashtags?: string[]
  mentionAccounts?: string[]
  scheduleTimezone?: string
  autoRepost?: boolean
}
```

## Integration Implementation Plan

### Phase 1: Core Infrastructure

#### 1. Base Platform Interface
```typescript
abstract class BasePlatform {
  abstract type: string
  abstract name: string
  abstract authenticate(config: any): Promise<AuthResult>
  abstract validateConfig(config: any): Promise<ValidationResult>
  abstract publish(content: string, config: any): Promise<PublishResult>
  abstract scheduleContent(content: string, scheduledTime: Date, config: any): Promise<ScheduleResult>
  abstract getPublishedContent(id: string): Promise<ContentResult>
  abstract deleteContent(id: string): Promise<DeleteResult>
}
```

#### 2. Platform Factory
```typescript
class PlatformFactory {
  static create(type: string): BasePlatform {
    switch (type) {
      case 'mailchimp': return new MailChimpPlatform()
      case 'wordpress': return new WordPressPlatform()
      case 'twitter': return new TwitterPlatform()
      // ... other platforms
      default: throw new Error(`Unsupported platform: ${type}`)
    }
  }
}
```

### Phase 2: Email Platform Implementation

#### MailChimp Integration
```typescript
class MailChimpPlatform extends BasePlatform {
  type = 'mailchimp'
  name = 'MailChimp'

  async authenticate(config: EmailPlatformConfig): Promise<AuthResult> {
    // Test API key validity
    const response = await fetch(`https://us1.api.mailchimp.com/3.0/ping`, {
      headers: {
        'Authorization': `Bearer ${config.apiKey}`
      }
    })
    return { success: response.ok }
  }

  async publish(content: string, config: EmailPlatformConfig): Promise<PublishResult> {
    // Create and send campaign
    const campaign = await this.createCampaign(content, config)
    const result = await this.sendCampaign(campaign.id, config)
    return {
      success: result.success,
      platformId: campaign.id,
      url: campaign.archive_url
    }
  }

  private async createCampaign(content: string, config: EmailPlatformConfig) {
    // MailChimp API implementation
    const subject = this.extractSubject(content)
    const htmlContent = this.formatForEmail(content)
    
    return fetch(`https://us1.api.mailchimp.com/3.0/campaigns`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${config.apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        type: 'regular',
        recipients: { list_id: config.listId },
        settings: {
          subject_line: subject,
          from_name: config.fromName,
          reply_to: config.replyTo
        }
      })
    })
  }
}
```

### Phase 3: WordPress Integration

#### WordPress Platform Implementation
```typescript
class WordPressPlatform extends BasePlatform {
  type = 'wordpress'
  name = 'WordPress'

  async authenticate(config: WordPressPlatformConfig): Promise<AuthResult> {
    const auth = this.buildAuthHeader(config)
    const response = await fetch(`${config.siteUrl}/wp-json/wp/v2/users/me`, {
      headers: { 'Authorization': auth }
    })
    return { success: response.ok }
  }

  async publish(content: string, config: WordPressPlatformConfig): Promise<PublishResult> {
    const post = this.formatForWordPress(content, config)
    const auth = this.buildAuthHeader(config)
    
    const response = await fetch(`${config.siteUrl}/wp-json/wp/v2/posts`, {
      method: 'POST',
      headers: {
        'Authorization': auth,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(post)
    })

    const result = await response.json()
    return {
      success: response.ok,
      platformId: result.id.toString(),
      url: result.link
    }
  }

  private formatForWordPress(content: string, config: WordPressPlatformConfig) {
    const title = this.extractTitle(content)
    const body = this.formatContent(content)
    
    return {
      title,
      content: body,
      status: config.defaultStatus,
      categories: config.defaultCategory ? [config.defaultCategory] : [],
      tags: config.defaultTags || []
    }
  }
}
```

### Phase 4: Settings Management UI

#### Platform Settings Page Structure
```
/settings/platforms
├── index.tsx                    # Platform overview
├── components/
│   ├── PlatformCard.tsx        # Individual platform card
│   ├── ConfigurationModal.tsx  # Platform setup modal
│   ├── AuthFlow.tsx           # OAuth/API key flow
│   └── TestConnection.tsx     # Connection testing
└── [platform]/
    └── configure.tsx          # Platform-specific config
```

#### Settings UI Components
```typescript
// Platform Configuration Modal
interface ConfigurationModalProps {
  platform: PlatformType
  existingConfig?: PlatformConfig
  onSave: (config: PlatformConfig) => Promise<void>
  onCancel: () => void
}

// Dynamic Form Based on Platform
function PlatformConfigForm({ platform }: { platform: string }) {
  switch (platform) {
    case 'mailchimp':
      return <MailChimpConfigForm />
    case 'wordpress':
      return <WordPressConfigForm />
    default:
      return <SocialMediaConfigForm platform={platform} />
  }
}
```

## API Endpoints Design

### Platform Configuration API
```typescript
// GET /api/platforms/configurations
// POST /api/platforms/configurations
// PUT /api/platforms/configurations/:id
// DELETE /api/platforms/configurations/:id
// POST /api/platforms/test-connection
// POST /api/platforms/authenticate
```

### Enhanced Publishing API
```typescript
// POST /api/publishing/publish
interface PublishRequest {
  derivativeId: number
  platformConfigId: number
  scheduledTime?: string
  additionalOptions?: Record<string, any>
}

// GET /api/publishing/status/:id
// DELETE /api/publishing/cancel/:id
```

## Content Adaptation Strategies

### Email Content Formatting
- **Subject Line Extraction**: Use first line or specific marker
- **HTML Template**: Convert markdown to responsive email HTML
- **Image Handling**: Upload to CDN, embed in email
- **Link Tracking**: Add UTM parameters automatically
- **Personalization**: Insert merge tags for MailChimp

### WordPress Content Formatting
- **Title Extraction**: Use H1 or first line
- **Content Structure**: Convert to WordPress blocks
- **Featured Image**: Auto-set from content images
- **SEO Optimization**: Auto-generate meta descriptions
- **Categories/Tags**: Auto-suggest based on content

### Social Media Enhancements
- **Platform Optimization**: Current system + enhanced hashtag suggestions
- **Image Optimization**: Auto-resize for platform requirements
- **Link Shortening**: Integrate bit.ly or custom shortener
- **Engagement Tracking**: Store platform-specific metrics

## Security Considerations

### Credential Management
```typescript
class CredentialManager {
  static encrypt(data: any): string {
    // Use AES encryption for sensitive data
    return CryptoJS.AES.encrypt(JSON.stringify(data), process.env.SECRET_KEY).toString()
  }
  
  static decrypt(encryptedData: string): any {
    // Decrypt credentials when needed
    const bytes = CryptoJS.AES.decrypt(encryptedData, process.env.SECRET_KEY)
    return JSON.parse(bytes.toString(CryptoJS.enc.Utf8))
  }
}
```

### OAuth Flow Implementation
```typescript
class OAuthManager {
  static generateAuthUrl(platform: string, redirectUri: string): string {
    // Generate OAuth URL with proper scopes
  }
  
  static exchangeCodeForToken(platform: string, code: string): Promise<TokenResponse> {
    // Exchange authorization code for access token
  }
  
  static refreshToken(platform: string, refreshToken: string): Promise<TokenResponse> {
    // Refresh expired tokens
  }
}
```

## Deployment & Monitoring

### Environment Variables
```env
# Email Platforms
MAILCHIMP_CLIENT_ID=
MAILCHIMP_CLIENT_SECRET=
CONSTANT_CONTACT_API_KEY=
SENDGRID_API_KEY=

# CMS Platforms
WORDPRESS_OAUTH_CLIENT_ID=
WORDPRESS_OAUTH_CLIENT_SECRET=

# Social Media (existing)
TWITTER_API_KEY=
LINKEDIN_CLIENT_ID=
FACEBOOK_APP_ID=

# Security
ENCRYPTION_SECRET_KEY=
OAUTH_STATE_SECRET=
```

### Monitoring & Analytics
- **API Rate Limits**: Track usage per platform
- **Success Rates**: Monitor publishing success/failure rates
- **Performance Metrics**: Track publishing times
- **Error Logging**: Detailed error tracking per platform
- **User Analytics**: Track most used platforms/features

## Implementation Priority

### Phase 1 (Immediate - 2 weeks)
1. ✅ Database schema updates
2. ✅ Base platform infrastructure
3. ✅ Settings management UI foundation
4. ✅ MailChimp basic integration

### Phase 2 (Month 1)
1. ✅ WordPress integration
2. ✅ Enhanced social media configs
3. ✅ OAuth flow implementation
4. ✅ Content adaptation algorithms

### Phase 3 (Month 2)
1. ✅ Additional email providers
2. ✅ Advanced scheduling features
3. ✅ Analytics dashboard
4. ✅ Mobile app integration

### Phase 4 (Month 3+)
1. ✅ Enterprise features
2. ✅ Team collaboration
3. ✅ White-label solutions
4. ✅ API for third-party integrations

## Success Metrics

- **Platform Adoption**: % of users who configure each platform
- **Publishing Success Rate**: % of successful publications per platform
- **Time to Configure**: Average time to set up a new platform
- **User Retention**: Users who continue using multi-platform features
- **Content Performance**: Engagement metrics across platforms

This architecture provides a scalable, secure, and user-friendly foundation for comprehensive multi-platform content publishing with proper authentication and configuration management.