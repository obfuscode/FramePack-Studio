import gradio as gr
import os
import time
import datetime
from modules.video_queue import JobStatus

def debug_job_data(jobs):
    """Debug function to inspect all available job data"""
    if not jobs:
        print("No jobs to inspect")
        return
    
    print("\n" + "="*50)
    print("DEBUG: JOB DATA INSPECTION")
    print("="*50)
    
    for i, job in enumerate(jobs):
        print(f"\n--- Job {i+1} ---")
        print(f"Job ID: {getattr(job, 'id', 'N/A')}")
        print(f"Job Type: {type(job).__name__}")
        
        # Get all attributes
        all_attrs = dir(job)
        # Filter out built-in attributes and methods
        user_attrs = [attr for attr in all_attrs if not attr.startswith('_') and not callable(getattr(job, attr))]
        
        print(f"Available attributes ({len(user_attrs)}):")
        for attr in sorted(user_attrs):
            try:
                value = getattr(job, attr)
                # Don't truncate the "params" attribute - show full value
                if attr == "params":
                    print(f"  {attr}: {value}")
                else:
                    # Truncate long values for readability
                    if isinstance(value, str) and len(value) > 100:
                        value = value[:100] + "..."
                    elif isinstance(value, (list, dict)) and len(str(value)) > 100:
                        value = str(value)[:100] + "..."
                    print(f"  {attr}: {value}")
            except Exception as e:
                print(f"  {attr}: <Error accessing: {e}>")
    
    print("\n" + "="*50)

def format_queue_status(jobs):
    rows = []
    for job in jobs:
        created = time.strftime('%H:%M:%S', time.localtime(job.created_at)) if job.created_at else ""
        started = time.strftime('%H:%M:%S', time.localtime(job.started_at)) if job.started_at else ""
        completed = time.strftime('%H:%M:%S', time.localtime(job.completed_at)) if job.completed_at else ""
        elapsed_time = ""
        if job.started_at:
            end_time = job.completed_at or time.time()
            elapsed_seconds = end_time - job.started_at
            status_suffix = "" if job.completed_at else " (running)"
            elapsed_time = f"{elapsed_seconds:.2f}s{status_suffix}"
        generation_type = getattr(job, 'generation_type', 'Original')
        thumbnail = getattr(job, 'thumbnail', None)
        thumbnail_html = f'<img src="{thumbnail}" width="64" height="64" style="object-fit: contain;">' if thumbnail else ""
        rows.append([job.id[:6] + '...', generation_type, job.status.value, created, started, completed, elapsed_time, thumbnail_html])
    return rows

def format_queue_cards(jobs):
    """Generate HTML cards for job queue display"""
    # DEBUG: Uncomment the next line to see all available job data
    debug_job_data(jobs)
    
    if not jobs:
        return '<div style="text-align: center; padding: 20px; color: #666;">No jobs in queue</div>'
    
    cards_html = '<div style="padding: 16px;">'

    # Default values for comparison
    default_values = {
        'latent_window_size': 9,
        'steps': 25,
        'cfg': 1.0,
        'gs': 10.0,
        'rs': 0.0,
        'total_second_length': 6,
        'resolutionW': 640,
        'resolutionH': 640,
        'blend_sections': 4,
        'cache_type': 'MagCache',
        'use_magcache': True,
        'use_teacache': False,
        'magcache_threshold': 0.1,
        'magcache_max_consecutive_skips': 2,
        'magcache_retention_ratio': 0.25,
        'teacache_num_steps': 25,
        'teacache_rel_l1_thresh': 0.15,
        'latent_type': 'Noise',
        'combine_with_source': True,
        'num_cleaned_frames': 5
    }

    for job in jobs:
        # Get job parameters
        params = job.params or {}
        
        # Get prompt
        prompt = params.get('prompt_text', params.get('prompt', 'No prompt available'))
        if not prompt or prompt.strip() == '':
            prompt = 'No prompt available'
        
        prompt_short = (prompt[:255] + '...') if len(prompt) > 255 else prompt
        prompt_needs_expand = len(prompt) > 255

        # Extract all available data from job object
        job_id = getattr(job, 'id', 'Unknown')[:8] + '...'
        generation_type = getattr(job, 'generation_type', 'Original')
        status = getattr(job, 'status', JobStatus.PENDING).value
        thumbnail = getattr(job, 'thumbnail', None)
        
        # Time formatting
        created = time.strftime('%H:%M:%S', time.localtime(job.created_at)) if getattr(job, 'created_at', None) else "N/A"
        started = time.strftime('%H:%M:%S', time.localtime(job.started_at)) if getattr(job, 'started_at', None) else "N/A"
        completed = time.strftime('%H:%M:%S', time.localtime(job.completed_at)) if getattr(job, 'completed_at', None) else "N/A"
        
        # Calculate elapsed time
        elapsed_time = ""
        if getattr(job, 'started_at', None):
            end_time = getattr(job, 'completed_at', None) or time.time()
            elapsed_seconds = end_time - job.started_at
            status_suffix = "" if getattr(job, 'completed_at', None) else " (running)"
            elapsed_time = f"{elapsed_seconds:.2f}s{status_suffix}"
        
        # Queue position for pending jobs
        queue_position = getattr(job, 'queue_position', None)
        
        # Additional job data
        steps = params.get('steps', 'N/A')
        seed = params.get('seed', 'N/A')
        resolution = f"{params.get('resolutionW', 'N/A')}x{params.get('resolutionH', 'N/A')}"
        duration = f"{params.get('total_second_length', 'N/A')}s"
        cache_type = 'MagCache' if params.get('use_magcache', False) else 'TeaCache' if params.get('use_teacache', False) else 'None'
        
        # Status-based styling
        status_colors = {
            'PENDING': '#ffa500',
            'RUNNING': '#007bff', 
            'COMPLETED': '#28a745',
            'FAILED': '#dc3545',
            'CANCELLED': '#6c757d'
        }
        status_color = status_colors.get(status.upper(), '#6c757d')

        status_icon = {
            'PENDING': '⏳',
            'RUNNING': '🔄',
            'COMPLETED': '✅',
            'FAILED': '❌',
            'CANCELLED': '❌'
        }[status.upper()]

        # Generate settings pills for non-default values
        settings_pills = []
        
        # Helper function to add setting pill if different from default
        def add_setting_if_different(key, label, value, default_value):
            if value is not None and value != default_value:
                settings_pills.append(f'''
                    <div class="setting-pill">
                        <div class="setting-pill-label">{label}</div>
                        <div class="setting-pill-value">{value}</div>
                    </div>
                ''')
        
        # Check each setting against defaults
        add_setting_if_different('latent_window_size', 'LWS', params.get('latent_window_size'), default_values['latent_window_size'])
        add_setting_if_different('steps', 'Steps', params.get('steps'), default_values['steps'])
        add_setting_if_different('cfg', 'CFG', params.get('cfg'), default_values['cfg'])
        add_setting_if_different('gs', 'DCS', params.get('gs'), default_values['gs'])
        add_setting_if_different('rs', 'RS', params.get('rs'), default_values['rs'])
        add_setting_if_different('total_second_length', 'Length', f"{params.get('total_second_length')}s", f"{default_values['total_second_length']}s")
        
        # Resolution
        res_w = params.get('resolutionW')
        res_h = params.get('resolutionH')
        if res_w and res_h and (res_w != default_values['resolutionW'] or res_h != default_values['resolutionH']):
            settings_pills.append(f'''
                <div class="setting-pill">
                    <div class="setting-pill-label">Size</div>
                    <div class="setting-pill-value">{res_w}x{res_h}</div>
                </div>
            ''')
        
        add_setting_if_different('blend_sections', 'Blend', params.get('blend_sections'), default_values['blend_sections'])
        
        # Cache settings
        cache_type = 'None'
        if params.get('use_magcache', False):
            cache_type = 'MagCache'
        elif params.get('use_teacache', False):
            cache_type = 'TeaCache'
        
        if cache_type != default_values['cache_type']:
            settings_pills.append(f'''
                <div class="setting-pill">
                    <div class="setting-pill-label">Cache</div>
                    <div class="setting-pill-value">{cache_type}</div>
                </div>
            ''')
        
        # Cache-specific settings
        if cache_type == 'MagCache':
            add_setting_if_different('magcache_threshold', 'MagThresh', params.get('magcache_threshold'), default_values['magcache_threshold'])
            add_setting_if_different('magcache_max_consecutive_skips', 'MagSkips', params.get('magcache_max_consecutive_skips'), default_values['magcache_max_consecutive_skips'])
            add_setting_if_different('magcache_retention_ratio', 'MagRet', params.get('magcache_retention_ratio'), default_values['magcache_retention_ratio'])
        elif cache_type == 'TeaCache':
            add_setting_if_different('teacache_num_steps', 'TeaSteps', params.get('teacache_num_steps'), default_values['teacache_num_steps'])
            add_setting_if_different('teacache_rel_l1_thresh', 'TeaThresh', params.get('teacache_rel_l1_thresh'), default_values['teacache_rel_l1_thresh'])
        
        add_setting_if_different('latent_type', 'Latent', params.get('latent_type'), default_values['latent_type'])
        add_setting_if_different('combine_with_source', 'Combine', params.get('combine_with_source'), default_values['combine_with_source'])
        add_setting_if_different('num_cleaned_frames', 'Frames', params.get('num_cleaned_frames'), default_values['num_cleaned_frames'])
        
        # Seed (always show if present)
        seed = params.get('seed')
        if seed is not None:
            settings_pills.append(f'''
                <div class="setting-pill">
                    <div class="setting-pill-label">Seed</div>
                    <div class="setting-pill-value">{seed}</div>
                </div>
            ''')
        
        # Generation type
        generation_type = getattr(job, 'generation_type', 'Original')
        if generation_type != 'Original':
            settings_pills.append(f'''
                <div class="setting-pill">
                    <div class="setting-pill-label">Type</div>
                    <div class="setting-pill-value">{generation_type}</div>
                </div>
            ''')
        
        safe_job_id = job.id.replace('-', '')
        expand_button = f'<button class="queue-prompt-expand" id="prompt-toggle-{safe_job_id}" onclick="togglePrompt(\'{safe_job_id}\')">Expand +</button>' if prompt_needs_expand else ''
                
        # Generate card HTML - 3 columns: status, prompt and params, and thumbnail / output video link
        card_html = f'''
        <div style="display: flex; flex-direction: row; gap: 16px; justify-content: space-between; border: 1px solid #ddd; border-radius: 8px; padding: 16px; background: var(--border-color-primary); box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <div class="queue-status-indicator" style="background: {status_color}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;">
                <div class="status-icon">{status_icon}</div>
            </div>
            <div class="queue-card-content">
                <div class="queue-prompt-section">
                    <p class="queue-prompt-text">
                        <span id="prompt-short-{job_id}">{prompt_short}</span>
                        <span id="prompt-full-{job_id}" style="display: none;">{prompt}</span>
                    </p>
                    {expand_button}
                </div>
                <div class="queue-settings-section">
                    {''.join(settings_pills)}
                </div>
            </div>
            <div class="queue-media-section">
                <div>
                    {f'<img src="{thumbnail}" alt="Preview">' if thumbnail else '<div class="queue-preview-placeholder">No Preview</div>'}
                </div>
            </div>
            
            <div style="margin-bottom: 12px;">
                <strong>Type:</strong> {generation_type}<br>
                <strong>Steps:</strong> {steps} | <strong>Seed:</strong> {seed}<br>
                <strong>Resolution:</strong> {resolution} | <strong>Duration:</strong> {duration}
            </div>
            
            <div style="margin-bottom: 12px; font-size: 12px; color: #666;">
                <strong>Created:</strong> {created}<br>
                <strong>Started:</strong> {started}<br>
                <strong>Completed:</strong> {completed}<br>
                <strong>Elapsed:</strong> {elapsed_time}
                {f'<br><strong>Queue Position:</strong> #{queue_position}' if queue_position is not None else ''}
            </div>
            
            {f'<div style="text-align: center;"><img src="{thumbnail}" style="max-width: 100%; max-height: 120px; object-fit: contain; border-radius: 4px;"></div>' if thumbnail else ''}
        </div>
        '''
        
        cards_html += card_html
    
    cards_html += '</div>'
    return cards_html

def update_queue_status_with_thumbnails():
    try:
        from __main__ import job_queue
        jobs = job_queue.get_all_jobs()
        for job in jobs:
            if job.status == JobStatus.PENDING:
                job.queue_position = job_queue.get_queue_position(job.id)
        if job_queue.current_job:
            job_queue.current_job.status = JobStatus.RUNNING
        return format_queue_cards(jobs)
    except ImportError:
        print("Error: Could not import job_queue. Queue status update might fail.")
        return '<div style="text-align: center; padding: 20px; color: #dc3545;">Error: Could not load job queue</div>'
    except Exception as e:
        print(f"Error updating queue status: {e}")
        return f'<div style="text-align: center; padding: 20px; color: #dc3545;">Error updating queue: {str(e)}</div>'

def create_queue_ui():
    with gr.Row():
        with gr.Column():
            with gr.Row() as queue_controls_row:
                refresh_button = gr.Button("🔄 Refresh Queue")
                load_queue_button = gr.Button("▶️ Resume Queue")
                queue_export_button = gr.Button("📦 Export Queue")
                clear_complete_button = gr.Button("🧹 Clear Completed Jobs", variant="secondary")
                clear_queue_button = gr.Button("❌ Cancel Queued Jobs", variant="stop")
            with gr.Row():
                import_queue_file = gr.File(
                    label="Import Queue",
                    file_types=[".json", ".zip"],
                    type="filepath",
                    visible=True,
                    elem_classes="short-import-box"
                )
            with gr.Row(visible=False) as confirm_cancel_row:
                gr.Markdown("### Are you sure you want to cancel all pending jobs?")
                confirm_cancel_yes_btn = gr.Button("❌ Yes, Cancel All", variant="stop")
                confirm_cancel_no_btn = gr.Button("↩️ No, Go Back")
            with gr.Row():
                queue_status = gr.HTML(
                    value='<div style="text-align: center; padding: 20px; color: #666;">Loading queue...</div>',
                    label="Job Queue"
                )
            with gr.Accordion("Queue Documentation", open=False):
                gr.Markdown("""
                ## Queue Tab Guide
                
                This tab is for managing your generation jobs.
                
                - **Refresh Queue**: Update the job list.
                - **Cancel Queue**: Stop all pending jobs.
                - **Clear Complete**: Remove finished, failed, or cancelled jobs from the list.
                - **Load Queue**: Load jobs from the default `queue.json`.
                - **Export Queue**: Save the current job list and its images to a zip file.
                - **Import Queue**: Load a queue from a `.json` or `.zip` file.
                """)
    return {
        "queue_status": queue_status,
        "refresh_button": refresh_button,
        "load_queue_button": load_queue_button,
        "queue_export_button": queue_export_button,
        "clear_complete_button": clear_complete_button,
        "clear_queue_button": clear_queue_button,
        "import_queue_file": import_queue_file,
        "queue_controls_row": queue_controls_row,
        "confirm_cancel_row": confirm_cancel_row,
        "confirm_cancel_yes_btn": confirm_cancel_yes_btn,
        "confirm_cancel_no_btn": confirm_cancel_no_btn
    }

def connect_queue_events(q, g, f, job_queue):
    def clear_all_jobs():
        job_queue.clear_queue()
        return f["update_stats"]()

    def clear_completed_jobs():
        job_queue.clear_completed_jobs()
        return f["update_stats"]()

    def load_queue_from_json():
        job_queue.load_queue_from_json()
        return f["update_stats"]()

    def import_queue_from_file(file_path):
        if file_path:
            job_queue.load_queue_from_json(file_path)
        return f["update_stats"]()

    def export_queue_to_zip():
        job_queue.export_queue_to_zip()
        return f["update_stats"]()

    q["refresh_button"].click(fn=f["update_stats"], inputs=[], outputs=[q["queue_status"], q["queue_stats_display"]])
    q["clear_queue_button"].click(fn=lambda: (gr.update(visible=False), gr.update(visible=True)), outputs=[q["queue_controls_row"], q["confirm_cancel_row"]])
    q["confirm_cancel_no_btn"].click(fn=lambda: (gr.update(visible=True), gr.update(visible=False)), outputs=[q["queue_controls_row"], q["confirm_cancel_row"]])
    q["confirm_cancel_yes_btn"].click(fn=lambda: clear_all_jobs() + (gr.update(visible=True), gr.update(visible=False)), outputs=[q["queue_status"], q["queue_stats_display"], q["queue_controls_row"], q["confirm_cancel_row"]])
    q["clear_complete_button"].click(fn=clear_completed_jobs, inputs=[], outputs=[q["queue_status"], q["queue_stats_display"]])
    q["queue_export_button"].click(fn=export_queue_to_zip, inputs=[], outputs=[q["queue_status"], q["queue_stats_display"]])
    q["load_queue_button"].click(fn=load_queue_from_json, inputs=[], outputs=[q["queue_status"], q["queue_stats_display"]]).then(fn=f["check_for_current_job"], outputs=[g["current_job_id"], g["result_video"], g["preview_image"], g["top_preview_image"], g["progress_desc"], g["progress_bar"]]).then(fn=f["create_latents_layout_update"], outputs=[g["top_preview_row"], g["preview_image"]])
    q["import_queue_file"].change(fn=import_queue_from_file, inputs=[q["import_queue_file"]], outputs=[q["queue_status"], q["queue_stats_display"]]).then(fn=f["check_for_current_job"], outputs=[g["current_job_id"], g["result_video"], g["preview_image"], g["top_preview_image"], g["progress_desc"], g["progress_bar"]]).then(fn=f["create_latents_layout_update"], outputs=[g["top_preview_row"], g["preview_image"]])