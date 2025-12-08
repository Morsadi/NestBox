Dropzone.autoDiscover = false;

document.addEventListener('DOMContentLoaded', () => {
	const elements = {
		dropzoneEl: document.querySelector('#myDropzone'),
		fileQueueEl: document.querySelector('#file-queue'),
		emptyQueueMessage: document.querySelector('#empty-queue-message'),
		networkAlert: document.querySelector('#network-alert'),
		queuePanel: document.querySelector('.queue-panel'),
		queueCount: document.querySelector('#queue-count'),
		queueTotal: document.querySelector('#queue-total'),
	};

	// Dropzone initialization
	const myDropzone = new Dropzone(elements.dropzoneEl, {
		url: '/upload/',
		paramName: 'file',
		maxFilesize: 20480,
		chunking: true,
		forceChunking: true,
		chunkSize: 16 * 1024 * 1024,
		parallelUploads: 4,
		parallelChunkUploads: true,
		retryChunks: true,
		retryChunksLimit: 3,
		timeout: 0,
		previewsContainer: '#dropzone-previews',
		clickable: true,
		dictDefaultMessage: 'Drop files here or click to upload',
		autoQueue: false,
	});

	if (!elements.dropzoneEl) return;

	let disconnectDetected = false;
	let lastErrorTime = null;
	let completedUploads = 0;

	// Formats bytes into human-readable units
	const formatBytes = (bytes, decimals = 2) => {
		if (bytes === 0) return '0 Bytes';
		const k = 1024;
		const dm = decimals < 0 ? 0 : decimals;
		const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
		const i = Math.floor(Math.log(bytes) / Math.log(k));
		return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
	};

	// Upload status definitions
	const STATUS = {
		INITIAL: { icon: '<i class="fa fa-spinner fa-spin"></i>', colorClass: 'text-text', text: 'Checking status...' },
		READY_TO_START: { icon: '<i class="fa fa-upload"></i>', colorClass: 'text-primary', text: (size) => `Ready to start upload (${formatBytes(size)})` },
		READY_TO_RESUME: { icon: '<i class="fa fa-redo"></i>', colorClass: 'text-warning', text: (uploaded, total) => `Ready to resume: ${formatBytes(uploaded)} of ${formatBytes(total)}` },
		UPLOADING_PROGRESS: { icon: '<i class="fa fa-spinner fa-spin"></i>', colorClass: 'text-primary', text: (progress, total) => `Uploading: ${Math.round(progress)}% of ${formatBytes(total)}` },
		UPLOADING: { icon: '<i class="fa fa-spinner fa-spin"></i>', colorClass: 'text-primary', text: (uploaded, total) => `Uploading: ${formatBytes(total)}` },
		INTERRUPTED: { icon: '<i class="fa fa-exclamation-triangle"></i>', colorClass: 'text-danger', text: 'Connection interrupted. Retrying...' },
		COMPLETE: { icon: '<i class="fa fa-check-circle"></i>', colorClass: 'text-success', text: (size) => `Upload Complete: ${formatBytes(size)}` },
		ALREADY_EXISTS: { icon: '<i class="fa fa-exclamation-circle"></i>', colorClass: 'text-warning', text: (size) => `Skipped: File already exists (${formatBytes(size)})` },
	};

	// Maps CSS class to its color variable
	const getStatusColor = (className) => {
		const map = {
			'text-primary': 'var(--color-primary)',
			'text-warning': 'var(--color-warning)',
			'text-success': 'var(--color-success)',
			'text-danger': 'var(--color-danger)',
			'text-text': 'var(--color-text)',
		};
		return map[className] || 'var(--color-text)';
	};

	// Updates the upload queue header counts
	const updateQueueHeader = () => {
		const totalFiles = myDropzone.files.length;
		elements.queueCount.textContent = completedUploads.toString().padStart(2, '0');
		elements.queueTotal.textContent = totalFiles.toString().padStart(2, '0');
	};

	// Updates file status text and color
	const updateFileStatus = (file, status, ...textArgs) => {
		const statusIconEl = document.querySelector(`#status-icon-${file.upload.uuid}`);
		const statusTextEl = document.querySelector(`#status-text-${file.upload.uuid}`);
		const text = typeof status.text === 'function' ? status.text(...textArgs) : status.text;

		if (statusIconEl) statusIconEl.innerHTML = status.icon;
		if (statusTextEl) {
			statusTextEl.textContent = text;
			statusTextEl.style.color = getStatusColor(status.colorClass);
		}
	};

	// Creates a queue list item for each file
	const createQueueItem = (file) => {
		// Show queuePanel for first file
		elements.queuePanel.classList.remove('hidden');

		if (elements.emptyQueueMessage) elements.emptyQueueMessage.classList.add('hidden');
		updateQueueHeader();

		const li = document.createElement('li');
		li.id = `file-${file.upload.uuid}`;
		li.className = 'list-item';
		li.innerHTML = `
			<div class="item-details">
				<span id="status-icon-${file.upload.uuid}" style="color: ${getStatusColor(STATUS.INITIAL.colorClass)};">${STATUS.INITIAL.icon}</span>
				<div class="status-text-wrapper">
					<span class="file-name">${file.name}</span>
					<span id="status-text-${file.upload.uuid}" class="status-text" style="color: ${getStatusColor(STATUS.INITIAL.colorClass)};">${STATUS.INITIAL.text}</span>
				</div>
			</div>`;
		elements.fileQueueEl.appendChild(li);
	};

	// Handles file addition, runs checkpoint and status checks
	myDropzone.on('addedfile', async (file) => {
		createQueueItem(file);
		const chunkSize = myDropzone.options.chunkSize;
		file.upload.bytesSent = 0;
		file.upload.totalChunkedBytes = 0;
		file.upload.existingChunks = 0;
		const destInput = document.querySelector('input[name="destination"]');

		try {
			const targetPath = destInput?.value;
			const checkpointRes = await fetch('/upload/checkpoint', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					filename: file.name,
					path: targetPath,
				}),
			});
			const checkpointData = await checkpointRes.json();

			if (checkpointData.exists) {
				file.status = Dropzone.SUCCESS;
				myDropzone.emit('complete', file);
				myDropzone.removeFile(file);
				updateFileStatus(file, STATUS.ALREADY_EXISTS, file.size);
				return;
			}

			const res = await fetch(`/upload/status?uuid=${file.upload.uuid}`);
			const data = await res.json();

			file.upload.existingChunks = data.uploaded_chunks || 0;
			const existingBytes = Math.min(file.upload.existingChunks * chunkSize, file.size);

			file.upload.bytesSent = existingBytes;
			file.upload.totalChunkedBytes = existingBytes;
			file.upload.progress = Math.min(100, Math.ceil((existingBytes / file.size) * 100));

			if (file.upload.existingChunks > 0) {
				updateFileStatus(file, STATUS.UPLOADING_PROGRESS, existingBytes, file.size);
			} else {
				updateFileStatus(file, STATUS.READY_TO_START, file.size);
			}

			myDropzone.enqueueFile(file);
		} catch (e) {
			console.error('Error checking file status:', e);
			updateFileStatus(file, STATUS.READY_TO_START, file.size);
			myDropzone.enqueueFile(file);
		}
	});

	// Adds destination path and skips redundant chunks
	myDropzone.on('sending', (file, xhr, formData) => {
		const idx = parseInt(formData.get('dzchunkindex'), 10);
		if (file.upload.existingChunks && idx < file.upload.existingChunks) return false;
		const destInput = document.querySelector('input[name="destination"]');
		if (destInput?.value) formData.append('destination', destInput.value);
	});

	// Handles upload errors and retry attempts
	myDropzone.on('error', (file, error, xhr) => {
		console.warn(`[INTERRUPTED] ${file.name} failed:`, error);
		updateFileStatus(file, STATUS.INTERRUPTED);
		const status = xhr ? xhr.status : 0;
		if ([409, 503, 0].includes(status)) {
			file._retryCount = (file._retryCount || 0) + 1;
			if (file._retryCount <= 2) {
				console.log(`[RETRYING] ${file.name} (attempt ${file._retryCount})`);
				setTimeout(() => {
					myDropzone.enqueueFile(file);
					myDropzone.processQueue();
				}, 3000);
			} else {
				console.warn(`[ABORTED] ${file.name} after 3 attempts`);
			}
		}
	});

	// Updates file progress display
	myDropzone.on('uploadprogress', (file, progress) => {
		if (!disconnectDetected) updateFileStatus(file, STATUS.UPLOADING_PROGRESS, progress, file.size);
	});

	// Marks files as completed
	myDropzone.on('success', async (file) => {
		if (file._mergeTriggered) return;
		file._mergeTriggered = true;

		if (file.upload.chunkIndex !== undefined && file.upload.chunkIndex + 1 < file.upload.totalChunkCount) {
			console.log(`[WAITING] ${file.name} still has chunks left.`);
			return;
		}

		completedUploads++;
		updateQueueHeader();
		updateFileStatus(file, STATUS.COMPLETE, file.size);
		const fileLi = document.querySelector(`#file-${file.upload.uuid}`);
		if (fileLi) fileLi.classList.add('item-success');
	});

	// Shows final confirmation once all uploads finish
	myDropzone.on('queuecomplete', async () => {
		const incomplete = myDropzone.files.filter((f) => f.status !== Dropzone.SUCCESS);
		if (incomplete.length) {
			console.warn(`⚠️ ${incomplete.length} files not fully uploaded.`);
			return;
		}
		console.log('✅ Upload complete.');
	});

	// Handles network reconnection
	window.addEventListener('online', () => {
		if (disconnectDetected) {
			const now = new Date();
			const elapsed = lastErrorTime ? ((now - lastErrorTime) / 1000).toFixed(1) : '?';
			elements.networkAlert.classList.add('hidden');
			myDropzone.processQueue();
			myDropzone.getUploadingFiles().forEach((file) => {
				updateFileStatus(file, STATUS.UPLOADING, elapsed, file.upload.bytesSent || 0, file.size);
			});
			disconnectDetected = false;
		}
	});
});
