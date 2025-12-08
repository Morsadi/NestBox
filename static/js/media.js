document.addEventListener('DOMContentLoaded', () => {
	// --- Preview Element Selectors ---
	const preview = document.getElementById('media-preview');
	const previewImg = document.getElementById('media-preview-img');
	const previewVideo = document.getElementById('media-preview-video');
	const closeBtn = document.querySelector('.media-preview-close');

	// --- Assets Selectors ---
	const clickableImages = document.querySelectorAll('.clickable-image');
	const clickableVideos = document.querySelectorAll('.clickable-video');
	const videosToLoad = document.querySelectorAll('.video-needs-loading');

	// --- Close Preview ---
	const closePreview = () => {
		preview.classList.add('hidden');

		// Clear Image
		previewImg.src = '';
		previewImg.style.display = 'none';

		// Clear Video (Stop playback)
		previewVideo.pause();
		previewVideo.src = '';
		previewVideo.style.display = 'none';
	};

	// ---  IMAGE Preview Logic ---
	clickableImages.forEach((img) => {
		img.addEventListener('click', (e) => {
			// Prevent default just in case it's inside a link
			e.preventDefault();
			const fullSrc = img.dataset.full;

			// UI Updates
			previewImg.src = fullSrc;
			previewImg.style.display = 'block';
			previewVideo.style.display = 'none';

			console.log('Showing image preview for:', fullSrc);
			preview.classList.remove('hidden');
		});
	});

	// --- VIDEO Preview Logic ---
	clickableVideos.forEach((video) => {
		video.addEventListener('click', (e) => {
			e.preventDefault(); // Prevent the thumbnail from playing inline

			// Get URL from data-full, fallback to current src if missing
			const fullSrc = video.dataset.full || video.currentSrc;

			// UI Updates
			previewVideo.src = fullSrc;
			previewVideo.style.display = 'block';
			previewImg.style.display = 'none';

			preview.classList.remove('hidden');

			// Auto-play the modal video
			previewVideo.play().catch((err) => console.log('Auto-play prevented:', err));
		});
	});

	closeBtn.addEventListener('click', closePreview);

	preview.addEventListener('click', (e) => {
		if (e.target === preview) {
			closePreview();
		}
	});

	// --- Thumbnail Loading Logic (Helps load videos on mobile) ---
	videosToLoad.forEach((video) => {
		// Check if the video is ready to draw a frame
		if (video.readyState >= 1) return;

		// Helps load the video on mobile devices
		video.load();

		// Safety check: attempt to seek to 0 after loading metadata
		video.addEventListener(
			'loadedmetadata',
			() => {
				if (video.currentTime !== 0) {
					video.currentTime = 0;
				}
			},
			{ once: true }
		);
	});
});
