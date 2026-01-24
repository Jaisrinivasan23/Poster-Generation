// Topmate API response types
export interface TopmateService {
  id: string;
  title: string;
  description: string;
  type: number;
  duration: number;
  charge: {
    amount: number;
    currency: string;
  };
  booking_count: number;
  promised_response_time?: string;
}

export interface TopmateBadge {
  id: string;
  name: string;
  description?: string;
  image_url?: string;
}

export interface TopmateProfile {
  user_id: string;
  username: string;
  first_name: string;
  last_name: string;
  display_name: string;
  profile_pic: string;
  bio: string;
  description?: string;
  linkedin_url?: string;
  instagram_url?: string;
  twitter_url?: string;
  timezone: string;

  // Metrics
  total_bookings: number;
  total_reviews: number;
  total_ratings: number;
  average_rating: number;
  expertise_count: number;
  expertise_category?: string;

  // Services
  services: TopmateService[];

  // Social proof
  badges: TopmateBadge[];
  liked_properties?: {
    friendly: number;
    helpful: number;
    insightful: number;
  };
  testimonials_count: number;
  ai_testimonial_summary?: string;

  // Meta
  meta_image?: string;
  join_date?: string;
}

// Poster generation types
export type PosterStyle =
  | 'professional'
  | 'creative'
  | 'minimal'
  | 'bold'
  | 'elegant'
  | 'tech'
  | 'playful';

export type PosterSize =
  | 'instagram-square'    // 1080x1080
  | 'instagram-portrait'  // 1080x1350
  | 'instagram-story'     // 1080x1920
  | 'linkedin-post'       // 1200x1200
  | 'twitter-post'        // 1200x675
  | 'facebook-post'       // 1200x630
  | 'a4-portrait'         // 2480x3508
  | 'custom';

export interface PosterDimensions {
  width: number;
  height: number;
}

export const POSTER_SIZE_DIMENSIONS: Record<Exclude<PosterSize, 'custom'>, PosterDimensions> = {
  'instagram-square': { width: 1080, height: 1080 },
  'instagram-portrait': { width: 1080, height: 1350 },
  'instagram-story': { width: 1080, height: 1920 },
  'linkedin-post': { width: 1200, height: 1200 },
  'twitter-post': { width: 1200, height: 675 },
  'facebook-post': { width: 1200, height: 630 },
  'a4-portrait': { width: 2480, height: 3508 },
};

export type PosterMode = 'single' | 'carousel';

export type GenerationMode = 'html' | 'image';

export interface PosterConfig {
  // Content source
  topmateUsername: string;

  // Design preferences
  style: PosterStyle;
  size: PosterSize;
  customDimensions?: PosterDimensions;
  mode: PosterMode;
  carouselSlides?: number; // 3-10 slides for carousel
  generationMode?: GenerationMode; // HTML or direct image generation (default: html)

  // Brand customization
  primaryColor?: string;
  secondaryColor?: string;
  accentColor?: string;

  // Content customization
  prompt: string;  // What the poster should highlight/focus on
  includeServices?: boolean;
  includeBadges?: boolean;
  includeTestimonials?: boolean;
  includeStats?: boolean;

  // Optional overrides
  customHeadline?: string;
  customTagline?: string;
  callToAction?: string;
}

export interface GeneratedPoster {
  // Generation mode determines which field is populated
  generationMode: GenerationMode;

  // HTML mode fields
  html?: string;
  css?: string;

  // Image mode fields
  imageUrl?: string;        // URL or data URL for the generated image
  imageData?: string;        // Optional: base64 image data

  dimensions: PosterDimensions;
  style: PosterStyle;
  topmateProfile: TopmateProfile;
  generatedAt: string;
  variantIndex?: number;
  slideIndex?: number; // For carousel slides
}

export interface CarouselResult {
  slides: GeneratedPoster[];
  mode: 'carousel';
}

export interface PosterGenerationRequest {
  config: PosterConfig;
  profile?: TopmateProfile;  // Can be pre-fetched or fetched by API
}

export interface PosterGenerationResponse {
  success: boolean;
  poster?: GeneratedPoster;
  error?: string;
}

// Bulk Generation Types
export type PosterFlowMode = 'single' | 'bulk' | 'template';

export interface BulkGenerationConfig {
  prompt: string;
  selectedRecords?: any[];
  size: PosterSize;
  model?: 'pro' | 'flash';
}

export interface BulkGenerationResult {
  userId: string;
  username: string;
  posterUrl: string;
  success: boolean;
  error?: string;
}

export interface BulkProgress {
  total: number;
  completed: number;
  failed: number;
  current?: string; // Current username being processed
}
