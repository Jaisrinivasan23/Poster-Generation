'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import EditPosterPage from '../components/EditPosterPage';

interface GeneratedPoster {
  html: string;
  description?: string;
  theme?: string;
  dimensions?: { width: number; height: number };
}

export default function EditPosterRoute() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [poster, setPoster] = useState<GeneratedPoster | null>(null);
  const [posterIndex, setPosterIndex] = useState<number>(0);

  useEffect(() => {
    // Get poster data from localStorage
    const storedPoster = localStorage.getItem('editingPoster');
    const storedIndex = localStorage.getItem('editingPosterIndex');

    if (storedPoster) {
      try {
        const posterData = JSON.parse(storedPoster);
        setPoster(posterData);
        setPosterIndex(storedIndex ? parseInt(storedIndex) : 0);
      } catch (error) {
        console.error('Failed to parse poster data:', error);
        router.push('/');
      }
    } else {
      // No poster data found, redirect to home
      router.push('/');
    }
  }, [router]);

  const handleBack = () => {
    // Clean up localStorage
    localStorage.removeItem('editingPoster');
    localStorage.removeItem('editingPosterIndex');
    // Go back to previous page (poster generation)
    router.back();
  };

  const handleSave = (updatedPoster: GeneratedPoster) => {
    // Save updated poster back to localStorage
    const storedPosters = localStorage.getItem('posters');
    if (storedPosters) {
      try {
        const posters = JSON.parse(storedPosters);
        posters[posterIndex] = updatedPoster;
        localStorage.setItem('posters', JSON.stringify(posters));
      } catch (error) {
        console.error('Failed to save poster:', error);
      }
    }

    // Clean up editing state
    localStorage.removeItem('editingPoster');
    localStorage.removeItem('editingPosterIndex');
  };

  if (!poster) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <svg className="animate-spin h-12 w-12 mx-auto mb-4 text-purple-600" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <p className="text-slate-600">Loading poster...</p>
        </div>
      </div>
    );
  }

  return (
    <EditPosterPage
      initialPoster={poster}
      posterIndex={posterIndex}
      onBack={handleBack}
      onSave={handleSave}
    />
  );
}
