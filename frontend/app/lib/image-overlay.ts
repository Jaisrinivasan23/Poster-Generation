import sharp from 'sharp';

/**
 * Overlay logo and profile picture on a base image
 * @param baseImageUrl - Base image as data URL or HTTP URL
 * @param logoUrl - Topmate logo as data URL
 * @param profilePicUrl - Profile picture URL (will be fetched and made circular)
 * @param dimensions - Image dimensions for positioning
 * @returns Composited image as data URL
 */
export async function overlayLogoAndProfile(
  baseImageUrl: string,
  logoUrl: string | null,
  profilePicUrl: string | null,
  dimensions: { width: number; height: number }
): Promise<string> {
  try {
    console.log('🎨 [OVERLAY] Starting image composition');

    // Convert base image to buffer
    let baseBuffer: Buffer;
    if (baseImageUrl.startsWith('data:image/')) {
      const base64Data = baseImageUrl.split(',')[1];
      baseBuffer = Buffer.from(base64Data, 'base64');
    } else {
      const response = await fetch(baseImageUrl);
      baseBuffer = Buffer.from(await response.arrayBuffer());
    }

    // Start with base image
    let composite = sharp(baseBuffer).resize(dimensions.width, dimensions.height, {
      fit: 'cover',
      position: 'center'
    });

    const overlays: Array<{ input: Buffer; top: number; left: number }> = [];

    // Add Topmate logo (top-right corner)
    if (logoUrl) {
      console.log('🏷️ [OVERLAY] Adding Topmate logo');
      try {
        const logoBase64 = logoUrl.startsWith('data:')
          ? logoUrl.split(',')[1]
          : Buffer.from(await (await fetch(logoUrl)).arrayBuffer()).toString('base64');
        const logoBuffer = Buffer.from(logoBase64, 'base64');

        // Resize logo to 70px width (proportional height)
        const resizedLogo = await sharp(logoBuffer)
          .resize(70, null, { fit: 'inside' })
          .png()
          .toBuffer();

        const logoMetadata = await sharp(resizedLogo).metadata();
        const logoHeight = logoMetadata.height || 20;

        // Position in top-right with 20px padding
        overlays.push({
          input: resizedLogo,
          top: 20,
          left: dimensions.width - 70 - 20
        });
        console.log('✅ [OVERLAY] Logo added at top-right');
      } catch (logoError) {
        console.error('❌ [OVERLAY] Failed to add logo:', logoError);
      }
    }

    // Add profile picture (bottom-left corner, circular)
    if (profilePicUrl) {
      console.log('📸 [OVERLAY] Adding profile picture');
      try {
        // Fetch profile picture
        const profileResponse = await fetch(profilePicUrl);
        const profileBuffer = Buffer.from(await profileResponse.arrayBuffer());

        // Create circular mask
        const size = 100; // Profile picture diameter
        const circularProfile = await sharp(profileBuffer)
          .resize(size, size, { fit: 'cover' })
          .composite([
            {
              input: Buffer.from(
                `<svg><circle cx="${size / 2}" cy="${size / 2}" r="${size / 2}" fill="white"/></svg>`
              ),
              blend: 'dest-in'
            }
          ])
          .png()
          .toBuffer();

        // Add white border
        const withBorder = await sharp(circularProfile)
          .extend({
            top: 3,
            bottom: 3,
            left: 3,
            right: 3,
            background: { r: 255, g: 255, b: 255, alpha: 1 }
          })
          .png()
          .toBuffer();

        // Position in bottom-left with 20px padding
        overlays.push({
          input: withBorder,
          top: dimensions.height - size - 3 - 3 - 20,
          left: 20
        });
        console.log('✅ [OVERLAY] Profile picture added at bottom-left');
      } catch (profileError) {
        console.error('❌ [OVERLAY] Failed to add profile picture:', profileError);
      }
    }

    // Apply all overlays
    if (overlays.length > 0) {
      composite = composite.composite(overlays);
    }

    // Convert to PNG buffer
    const finalBuffer = await composite.png().toBuffer();

    // Convert to data URL
    const dataUrl = `data:image/png;base64,${finalBuffer.toString('base64')}`;
    console.log('✅ [OVERLAY] Image composition complete');

    return dataUrl;
  } catch (error) {
    console.error('❌ [OVERLAY] Image overlay failed:', error);
    throw error;
  }
}

/**
 * Helper to fetch image and convert to buffer
 */
async function fetchImageAsBuffer(imageUrl: string): Promise<Buffer> {
  if (imageUrl.startsWith('data:image/')) {
    const base64Data = imageUrl.split(',')[1];
    return Buffer.from(base64Data, 'base64');
  } else {
    const response = await fetch(imageUrl);
    return Buffer.from(await response.arrayBuffer());
  }
}
