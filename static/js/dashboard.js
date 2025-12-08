document.addEventListener('DOMContentLoaded', () => {
	const indexDriveButtons = document.querySelectorAll('.index-drive-btn');
	const pollingTimers = {};

	indexDriveButtons.forEach((button) => {
		button.addEventListener('click', () => {
			const message = `Rescaning the drive will reconnect all files to the database. This may take a while depending on the drive size.`;
			const confirmed = confirm(`${message}\nAre you sure you want to resync the drive?`);
			if (!confirmed) return;

			startIndexing(button);
		});
	});

	function startIndexing(buttonElement) {
		const drivePath = buttonElement.getAttribute('data-drive-path');
		const driveId = buttonElement.getAttribute('data-drive-id');
		const encodedPath = encodeURIComponent(drivePath);
		const statusDiv = document.getElementById(`status-${driveId}`);

		buttonElement.disabled = true;
		statusDiv.innerHTML = 'Sending scan request...';

		fetch(`/drive/index/${encodedPath}`, { method: 'POST' })
			.then(async (response) => {
				if (!response.ok) {
					const errData = await response.json().catch(() => ({}));
					if (response.status === 400 && errData.message) {
						throw new Error(errData.message);
					}
					throw new Error(errData.message || `Server error: ${response.status}`);
				}
				return response.json();
			})
			.then((data) => {
				if (data.status === 'warning') {
					statusDiv.innerHTML = `⚠️ ${data.message}`;
					buttonElement.disabled = false;
					return;
				}

				// Scan started
				statusDiv.innerHTML = 'Scanning drive...';
				startIndexingPoll(driveId, statusDiv, buttonElement);
			})
			.catch((error) => {
				console.error('Scanning error:', error);
				statusDiv.innerHTML = `<i class="fas fa-exclamation-circle text-warning"></i> ${error.message}`;
				buttonElement.disabled = false;
			});
	}

	function startIndexingPoll(driveId, statusDiv, buttonElement) {
		// Clear previous timer if any
		if (pollingTimers[driveId]) {
			clearInterval(pollingTimers[driveId]);
		}

		pollingTimers[driveId] = setInterval(() => {
			fetch('/api/indexing')
				.then((res) => res.json())
				.then((data) => {
					if (!data.ok) {
						console.error('Indexing status error:', data.error);
						return;
					}

					if (data.is_indexing) {
						statusDiv.innerHTML = 'Scanning drive...';
					} else {
						clearInterval(pollingTimers[driveId]);
						statusDiv.innerHTML = '<i class="fas fa-check-circle text-success"></i> Scan complete.';
						buttonElement.disabled = false;
					}
				})
				.catch((err) => {
					console.error('Indexing status fetch failed:', err);
				});
		}, 3000);
	}
});
