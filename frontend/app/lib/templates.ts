// Curated template images for poster design reference
export interface Template {
  id: string;
  url: string;
  name: string;
  category: 'minimal' | 'bold' | 'gradient' | 'photo';
}

export interface CustomFont {
  id: string;
  font_name: string;
  font_family: string;
  file_url: string;
  file_format: string;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';

// Fetch dynamic templates from backend
export async function fetchDynamicTemplates(): Promise<Template[]> {
  try {
    const response = await fetch(`${BACKEND_URL}/api/template-images`);
    if (!response.ok) return [];
    const data = await response.json();
    return data.templates || [];
  } catch (error) {
    console.error('Failed to fetch dynamic templates:', error);
    return [];
  }
}

// Fetch custom fonts from backend
export async function fetchCustomFonts(): Promise<CustomFont[]> {
  try {
    const response = await fetch(`${BACKEND_URL}/api/custom-fonts`);
    if (!response.ok) return [];
    const data = await response.json();
    return data.fonts || [];
  } catch (error) {
    console.error('Failed to fetch custom fonts:', error);
    return [];
  }
}

// Get all templates (static + dynamic)
export async function getAllTemplates(): Promise<Template[]> {
  const dynamicTemplates = await fetchDynamicTemplates();
  return [...TEMPLATE_IMAGES, ...dynamicTemplates];
}

export const TEMPLATE_IMAGES: Template[] = [
  {
    id: 'template-1',
    url: 'https://res.cloudinary.com/topmate/image/upload/v1766481712/Poster%20Generator/59eee916b7a0bdb7f081ab2ed643c5b3_nvkthb.jpg',
    name: 'Template 1',
    category: 'bold',
  },
  {
    id: 'template-2',
    url: 'https://res.cloudinary.com/topmate/image/upload/v1766481712/Poster%20Generator/08451202f7975128326e835a1079de57_dyxsdb.jpg',
    name: 'Template 2',
    category: 'minimal',
  },
  {
    id: 'template-3',
    url: 'https://res.cloudinary.com/topmate/image/upload/v1766481712/Poster%20Generator/3bb094635351330d0bb6cff892702c20_y9izep.jpg',
    name: 'Template 3',
    category: 'gradient',
  },
];
