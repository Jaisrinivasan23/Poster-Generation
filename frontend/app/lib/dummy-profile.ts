// app/lib/dummy-profile.ts
// Generates realistic placeholder Topmate profile data for template preview generation

import { TopmateProfile } from '../types/poster';

/**
 * Creates a dummy Topmate profile with realistic placeholder data
 * Used for template generation before actual user data is available
 */
export function createDummyProfile(): TopmateProfile {
  return {
    // Basic Info
    user_id: "000000",
    username: "creator_username",
    display_name: "Creator Name",
    first_name: "Creator",
    last_name: "Name",
    profile_pic: "https://via.placeholder.com/150/4A90E2/FFFFFF?text=CN",
    bio: "Professional [expertise] helping clients achieve [goals]. Multiple years of experience in [field].",
    timezone: "Asia/Kolkata",

    // Realistic Metrics
    total_bookings: 487,
    total_reviews: 142,
    total_ratings: 142,
    average_rating: 4.7,
    expertise_count: 3,
    expertise_category: "Business & Marketing",

    // Sample Services
    services: [
      {
        id: "dummy-1",
        title: "1:1 Consultation Session",
        description: "Personalized guidance and strategy session tailored to your goals",
        type: 1,
        duration: 60,
        charge: { amount: 5000, currency: "INR" },
        booking_count: 120
      },
      {
        id: "dummy-2",
        title: "Quick Review Session",
        description: "Expert review and actionable feedback on your work",
        type: 1,
        duration: 30,
        charge: { amount: 2500, currency: "INR" },
        booking_count: 85
      },
      {
        id: "dummy-3",
        title: "Strategy Planning Call",
        description: "Comprehensive planning and roadmap development",
        type: 1,
        duration: 90,
        charge: { amount: 7500, currency: "INR" },
        booking_count: 62
      }
    ],

    // Badges
    badges: [
      {
        id: "verified",
        name: "Verified Expert",
        description: "Profile verified by Topmate"
      },
      {
        id: "top-rated",
        name: "Top Rated",
        description: "Consistently high ratings from clients"
      }
    ],

    // Social Proof Metrics
    liked_properties: {
      friendly: 45,
      helpful: 67,
      insightful: 52
    },

    testimonials_count: 38,
    ai_testimonial_summary: "Clients appreciate the clear communication, practical insights, and actionable guidance provided during sessions.",

    // Social Links (optional dummy data)
    linkedin_url: "https://linkedin.com/in/creator",
    twitter_url: "https://twitter.com/creator",
    instagram_url: "https://instagram.com/creator",

    // Meta
    join_date: "2022-01-15",
    meta_image: "https://via.placeholder.com/1200x630/4A90E2/FFFFFF?text=Creator+Profile"
  };
}

/**
 * Creates a dummy profile with custom placeholder text
 * Useful for testing different content scenarios
 */
export function createCustomDummyProfile(overrides: Partial<TopmateProfile>): TopmateProfile {
  const base = createDummyProfile();
  return {
    ...base,
    ...overrides
  };
}
