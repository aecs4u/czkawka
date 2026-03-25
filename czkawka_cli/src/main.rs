use std::path::PathBuf;
use std::sync::Arc;
use std::sync::atomic::AtomicBool;
use std::thread;

use clap::Parser;
use commands::Commands;
use crossbeam_channel::{Receiver, Sender, bounded};
use czkawka_core::common::config_cache_path::{print_infos_and_warnings, set_config_cache_path};
use czkawka_core::common::consts::DEFAULT_THREAD_SIZE;
use czkawka_core::common::image::register_image_decoding_hooks;
use czkawka_core::common::logger::{filtering_messages, print_version_mode, setup_logger};
use czkawka_core::common::progress_data::ProgressData;
use czkawka_core::common::set_number_of_threads;
use czkawka_core::common::tool_data::{CommonData, DeleteMethod};
use czkawka_core::common::traits::{AllTraits, FixingItems, PrintResults};
use czkawka_core::tools::bad_extensions::{BadExtensions, BadExtensionsFixParams, BadExtensionsParameters};
use czkawka_core::tools::bad_names::{BadNames, BadNamesParameters, NameFixerParams, NameIssues};
use czkawka_core::tools::big_file::{BigFile, BigFileParameters, SearchMode};
use czkawka_core::tools::broken_files::{BrokenFiles, BrokenFilesParameters, CheckedTypes};
use czkawka_core::tools::duplicate::{DuplicateFinder, DuplicateFinderParameters};
use czkawka_core::tools::empty_files::EmptyFiles;
use czkawka_core::tools::empty_folder::EmptyFolder;
use czkawka_core::tools::exif_remover::{ExifRemover, ExifRemoverParameters, ExifTagsFixerParams};
use czkawka_core::tools::invalid_symlinks::InvalidSymlinks;
use czkawka_core::tools::same_music::{SameMusic, SameMusicParameters};
use czkawka_core::tools::similar_documents::{SimilarDocuments, SimilarDocumentsParameters};
use czkawka_core::tools::similar_images::{SimilarImages, SimilarImagesParameters};
use czkawka_core::tools::similar_videos::{SimilarVideos, SimilarVideosParameters};
use czkawka_core::tools::temporary::Temporary;
use czkawka_core::tools::video_optimizer::{
    VideoCropFixParams, VideoCropParams, VideoCroppingMechanism, VideoOptimizer, VideoOptimizerFixParams, VideoOptimizerParameters, VideoTranscodeFixParams, VideoTranscodeParams,
};
use log::{debug, error, info};

use crate::commands::{
    Args, BadExtensionsArgs, BadNamesArgs, BiggestFilesArgs, BrokenFilesArgs, CommonCliItems, DMethod, DuplicatesArgs, EmptyFilesArgs, EmptyFoldersArgs, ExifRemoverArgs,
    InvalidSymlinksArgs, SDMethod, SameMusicArgs, SimilarDocumentsArgs, SimilarImagesArgs, SimilarVideosArgs, TemporaryArgs, VideoOptimizerArgs,
};
use crate::progress::{connect_progress, connect_progress_json};

mod commands;
mod progress;

#[derive(Debug)]
pub struct CliOutput {
    pub found_any_files: bool,
    pub ignored_error_code_on_found: bool,
    pub had_save_errors: bool,
    pub output: String,
}

struct ToolRunner<'a, T: AllTraits + PrintResults> {
    tool: T,
    common_cli_items: &'a CommonCliItems,
    reference_directories: Option<&'a Vec<PathBuf>>,
}

impl<'a, T: AllTraits + PrintResults> ToolRunner<'a, T> {
    fn new(tool: T, common_cli_items: &'a CommonCliItems) -> Self {
        Self {
            tool,
            common_cli_items,
            reference_directories: None,
        }
    }

    fn with_references(mut self, dirs: &'a Vec<PathBuf>) -> Self {
        self.reference_directories = Some(dirs);
        self
    }

    fn configure(mut self, f: impl FnOnce(&mut T)) -> Self {
        f(&mut self.tool);
        self
    }

    fn run(mut self, stop_flag: &Arc<AtomicBool>, progress_sender: &Sender<ProgressData>, tool_type: &str) -> CliOutput {
        set_common_settings(&mut self.tool, self.common_cli_items, self.reference_directories);
        self.tool.search(stop_flag, Some(progress_sender));
        save_and_write_results_to_writer(&self.tool, self.common_cli_items, tool_type)
    }

    fn run_with_fix(
        mut self,
        stop_flag: &Arc<AtomicBool>,
        progress_sender: &Sender<ProgressData>,
        tool_type: &str,
        fix_params: Option<T::FixParams>,
    ) -> CliOutput
    where
        T: FixingItems,
    {
        set_common_settings(&mut self.tool, self.common_cli_items, self.reference_directories);
        self.tool.search(stop_flag, Some(progress_sender));
        if let Some(params) = fix_params {
            self.tool.fix_items(stop_flag, Some(progress_sender), params);
        }
        save_and_write_results_to_writer(&self.tool, self.common_cli_items, tool_type)
    }
}

fn main() {
    register_image_decoding_hooks();
    if cfg!(debug_assertions) {
        use clap::CommandFactory;
        Args::command().debug_assert();
    }
    let command = Args::parse().command;

    let config_cache_path_set_result = set_config_cache_path("Czkawka", "Czkawka");
    setup_logger(true, "czkawka_cli", filtering_messages);
    print_version_mode("Czkawka cli");
    print_infos_and_warnings(config_cache_path_set_result.infos, config_cache_path_set_result.warnings);

    if cfg!(debug_assertions) {
        debug!("Running command - {command:?}");
    }

    let json_progress = command.get_json_progress();
    let tool_type = command.tool_type_name();
    let (progress_sender, progress_receiver): (Sender<ProgressData>, Receiver<ProgressData>) = bounded(256);
    let stop_flag = Arc::new(AtomicBool::new(false));
    let store_flag_cloned = stop_flag.clone();

    let calculate_thread = thread::Builder::new()
        .stack_size(DEFAULT_THREAD_SIZE)
        .spawn(move || match command {
            Commands::Duplicates(duplicates_args) => duplicates(duplicates_args, &stop_flag, &progress_sender, tool_type),
            Commands::EmptyFolders(empty_folders_args) => empty_folders(empty_folders_args, &stop_flag, &progress_sender, tool_type),
            Commands::BiggestFiles(biggest_files_args) => biggest_files(biggest_files_args, &stop_flag, &progress_sender, tool_type),
            Commands::EmptyFiles(empty_files_args) => empty_files(empty_files_args, &stop_flag, &progress_sender, tool_type),
            Commands::Temporary(temporary_args) => temporary(temporary_args, &stop_flag, &progress_sender, tool_type),
            Commands::SimilarImages(similar_images_args) => similar_images(similar_images_args, &stop_flag, &progress_sender, tool_type),
            Commands::SameMusic(same_music_args) => same_music(same_music_args, &stop_flag, &progress_sender, tool_type),
            Commands::InvalidSymlinks(invalid_symlinks_args) => invalid_symlinks(invalid_symlinks_args, &stop_flag, &progress_sender, tool_type),
            Commands::BrokenFiles(broken_files_args) => broken_files(broken_files_args, &stop_flag, &progress_sender, tool_type),
            Commands::SimilarVideos(similar_videos_args) => similar_videos(similar_videos_args, &stop_flag, &progress_sender, tool_type),
            Commands::BadExtensions(bad_extensions_args) => bad_extensions(bad_extensions_args, &stop_flag, &progress_sender, tool_type),
            Commands::BadNames(bad_names_args) => bad_names(bad_names_args, &stop_flag, &progress_sender, tool_type),
            Commands::VideoOptimizer(video_optimizer_args) => video_optimizer(video_optimizer_args, &stop_flag, &progress_sender, tool_type),
            Commands::ExifRemover(exif_remover_args) => exif_remover(exif_remover_args, &stop_flag, &progress_sender, tool_type),
            Commands::SimilarDocuments(similar_documents_args) => similar_documents(similar_documents_args, &stop_flag, &progress_sender, tool_type),
        })
        .expect("Failed to spawn calculation thread");

    ctrlc::set_handler(move || {
        if store_flag_cloned.load(std::sync::atomic::Ordering::SeqCst) {
            return;
        }
        info!("Got Ctrl+C signal, stopping...");
        store_flag_cloned.store(true, std::sync::atomic::Ordering::SeqCst);
    })
    .expect("Error setting Ctrl-C handler");

    if json_progress {
        connect_progress_json(&progress_receiver);
    } else {
        connect_progress(&progress_receiver);
    }

    let cli_output = calculate_thread.join().expect("Failed to join calculation thread");

    #[expect(clippy::print_stdout)]
    if !cli_output.output.is_empty() {
        println!("{}", cli_output.output);
    }

    if cli_output.had_save_errors {
        std::process::exit(1);
    } else if cli_output.found_any_files && !cli_output.ignored_error_code_on_found {
        std::process::exit(11);
    } else {
        std::process::exit(0);
    }
}

fn duplicates(duplicates: DuplicatesArgs, stop_flag: &Arc<AtomicBool>, progress_sender: &Sender<ProgressData>, tool_type: &str) -> CliOutput {
    let DuplicatesArgs {
        common_cli_items,
        reference_directories,
        minimal_file_size,
        maximal_file_size,
        minimal_cached_file_size,
        search_method,
        name_similarity_threshold,
        delete_method,
        hash_type,
        allow_hard_links,
        case_sensitive_name_comparison,
        minimal_prehash_cache_file_size,
        use_prehash_cache,
        no_self_compare,
    } = duplicates;

    let params = DuplicateFinderParameters::new(
        search_method,
        hash_type,
        use_prehash_cache,
        minimal_cached_file_size,
        minimal_prehash_cache_file_size,
        case_sensitive_name_comparison.case_sensitive_name_comparison,
    )
    .with_name_similarity_threshold(name_similarity_threshold)
    .with_no_self_compare(no_self_compare);

    ToolRunner::new(DuplicateFinder::new(params), &common_cli_items)
        .with_references(&reference_directories.reference_directories)
        .configure(|tool| {
            tool.set_minimal_file_size(minimal_file_size);
            tool.set_maximal_file_size(maximal_file_size);
            tool.set_hide_hard_links(!allow_hard_links.allow_hard_links);
            set_advanced_delete(tool, delete_method);
        })
        .run(stop_flag, progress_sender, tool_type)
}

fn empty_folders(empty_folders: EmptyFoldersArgs, stop_flag: &Arc<AtomicBool>, progress_sender: &Sender<ProgressData>, tool_type: &str) -> CliOutput {
    let EmptyFoldersArgs { common_cli_items, delete_method } = empty_folders;
    ToolRunner::new(EmptyFolder::new(), &common_cli_items)
        .configure(|tool| set_simple_delete(tool, delete_method))
        .run(stop_flag, progress_sender, tool_type)
}

fn biggest_files(biggest_files: BiggestFilesArgs, stop_flag: &Arc<AtomicBool>, progress_sender: &Sender<ProgressData>, tool_type: &str) -> CliOutput {
    let BiggestFilesArgs {
        common_cli_items,
        number_of_files,
        delete_method,
        smallest_mode,
    } = biggest_files;

    let big_files_mode = if smallest_mode { SearchMode::SmallestFiles } else { SearchMode::BiggestFiles };
    let params = BigFileParameters::new(number_of_files, big_files_mode);

    ToolRunner::new(BigFile::new(params), &common_cli_items)
        .configure(|tool| set_simple_delete(tool, delete_method))
        .run(stop_flag, progress_sender, tool_type)
}

fn empty_files(empty_files: EmptyFilesArgs, stop_flag: &Arc<AtomicBool>, progress_sender: &Sender<ProgressData>, tool_type: &str) -> CliOutput {
    let EmptyFilesArgs { common_cli_items, delete_method } = empty_files;
    ToolRunner::new(EmptyFiles::new(), &common_cli_items)
        .configure(|tool| set_simple_delete(tool, delete_method))
        .run(stop_flag, progress_sender, tool_type)
}

fn temporary(temporary: TemporaryArgs, stop_flag: &Arc<AtomicBool>, progress_sender: &Sender<ProgressData>, tool_type: &str) -> CliOutput {
    let TemporaryArgs { common_cli_items, delete_method } = temporary;
    ToolRunner::new(Temporary::new(), &common_cli_items)
        .configure(|tool| set_simple_delete(tool, delete_method))
        .run(stop_flag, progress_sender, tool_type)
}

fn similar_images(similar_images: SimilarImagesArgs, stop_flag: &Arc<AtomicBool>, progress_sender: &Sender<ProgressData>, tool_type: &str) -> CliOutput {
    let SimilarImagesArgs {
        common_cli_items,
        reference_directories,
        minimal_file_size,
        maximal_file_size,
        max_difference,
        hash_alg,
        image_filter,
        hash_size,
        delete_method,
        allow_hard_links,
        ignore_same_size,
    } = similar_images;

    let params = SimilarImagesParameters::new(max_difference, hash_size, hash_alg, image_filter, ignore_same_size.ignore_same_size);

    ToolRunner::new(SimilarImages::new(params), &common_cli_items)
        .with_references(&reference_directories.reference_directories)
        .configure(|tool| {
            tool.set_minimal_file_size(minimal_file_size);
            tool.set_maximal_file_size(maximal_file_size);
            tool.set_hide_hard_links(!allow_hard_links.allow_hard_links);
            set_advanced_delete(tool, delete_method);
        })
        .run(stop_flag, progress_sender, tool_type)
}

fn same_music(same_music: SameMusicArgs, stop_flag: &Arc<AtomicBool>, progress_sender: &Sender<ProgressData>, tool_type: &str) -> CliOutput {
    let SameMusicArgs {
        common_cli_items,
        reference_directories,
        delete_method,
        minimal_file_size,
        maximal_file_size,
        music_similarity,
        minimum_segment_duration,
        maximum_difference,
        search_method,
        approximate_comparison,
        compare_fingerprints_only_with_similar_titles,
        fuzzy_tag_comparison,
        tag_similarity_threshold,
    } = same_music;

    let mut params = SameMusicParameters::new(
        music_similarity,
        approximate_comparison,
        search_method,
        minimum_segment_duration,
        maximum_difference,
        compare_fingerprints_only_with_similar_titles,
    );
    params.fuzzy_tag_comparison = fuzzy_tag_comparison;
    params.tag_similarity_threshold = tag_similarity_threshold;

    ToolRunner::new(SameMusic::new(params), &common_cli_items)
        .with_references(&reference_directories.reference_directories)
        .configure(|tool| {
            tool.set_minimal_file_size(minimal_file_size);
            tool.set_maximal_file_size(maximal_file_size);
            set_advanced_delete(tool, delete_method);
        })
        .run(stop_flag, progress_sender, tool_type)
}

fn invalid_symlinks(invalid_symlinks: InvalidSymlinksArgs, stop_flag: &Arc<AtomicBool>, progress_sender: &Sender<ProgressData>, tool_type: &str) -> CliOutput {
    let InvalidSymlinksArgs { common_cli_items, delete_method } = invalid_symlinks;
    ToolRunner::new(InvalidSymlinks::new(), &common_cli_items)
        .configure(|tool| set_simple_delete(tool, delete_method))
        .run(stop_flag, progress_sender, tool_type)
}

fn broken_files(broken_files: BrokenFilesArgs, stop_flag: &Arc<AtomicBool>, progress_sender: &Sender<ProgressData>, tool_type: &str) -> CliOutput {
    let BrokenFilesArgs {
        common_cli_items,
        delete_method,
        checked_types,
    } = broken_files;

    let mut checked_type = CheckedTypes::NONE;
    for check_type in checked_types {
        checked_type |= check_type;
    }
    let params = BrokenFilesParameters::new(checked_type);

    ToolRunner::new(BrokenFiles::new(params), &common_cli_items)
        .configure(|tool| set_simple_delete(tool, delete_method))
        .run(stop_flag, progress_sender, tool_type)
}

fn similar_videos(similar_videos: SimilarVideosArgs, stop_flag: &Arc<AtomicBool>, progress_sender: &Sender<ProgressData>, tool_type: &str) -> CliOutput {
    let SimilarVideosArgs {
        reference_directories,
        common_cli_items,
        tolerance,
        minimal_file_size,
        maximal_file_size,
        delete_method,
        allow_hard_links,
        ignore_same_size,
        skip_forward_amount,
        crop_detect,
        scan_duration,
    } = similar_videos;

    let params = SimilarVideosParameters::new(
        tolerance,
        ignore_same_size.ignore_same_size,
        skip_forward_amount,
        scan_duration,
        crop_detect,
        false, // creating thumbnails in CLI, makes almost no sense
        10,    // creating thumbnails in CLI, makes almost no sense
        false, // creating thumbnails in CLI, makes almost no sense
        2,     // creating thumbnails in CLI, makes almost no sense
    );

    ToolRunner::new(SimilarVideos::new(params), &common_cli_items)
        .with_references(&reference_directories.reference_directories)
        .configure(|tool| {
            tool.set_minimal_file_size(minimal_file_size);
            tool.set_maximal_file_size(maximal_file_size);
            tool.set_hide_hard_links(!allow_hard_links.allow_hard_links);
            set_advanced_delete(tool, delete_method);
        })
        .run(stop_flag, progress_sender, tool_type)
}

fn bad_extensions(bad_extensions: BadExtensionsArgs, stop_flag: &Arc<AtomicBool>, progress_sender: &Sender<ProgressData>, tool_type: &str) -> CliOutput {
    let BadExtensionsArgs { common_cli_items, fix_extensions } = bad_extensions;
    ToolRunner::new(BadExtensions::new(BadExtensionsParameters::new()), &common_cli_items)
        .run_with_fix(stop_flag, progress_sender, tool_type, fix_extensions.then_some(BadExtensionsFixParams {}))
}

fn bad_names(bad_names: BadNamesArgs, stop_flag: &Arc<AtomicBool>, progress_sender: &Sender<ProgressData>, tool_type: &str) -> CliOutput {
    let BadNamesArgs {
        common_cli_items,
        delete_method,
        uppercase_extension,
        emoji_used,
        space_at_start_or_end,
        non_ascii_graphical,
        restricted_charset,
        remove_duplicated_non_alphanumeric,
        fix_names,
    } = bad_names;

    let restricted_charset_allowed = restricted_charset.and_then(|s| {
        let mut items: Vec<_> = s.chars().collect();
        items.sort_unstable();
        items.dedup();
        if items.is_empty() { None } else { Some(items) }
    });

    let name_issues = NameIssues {
        uppercase_extension,
        emoji_used,
        space_at_start_or_end,
        non_ascii_graphical,
        restricted_charset_allowed,
        remove_duplicated_non_alphanumeric,
    };

    let params = BadNamesParameters::new(name_issues);

    ToolRunner::new(BadNames::new(params), &common_cli_items)
        .configure(|tool| set_simple_delete(tool, delete_method))
        .run_with_fix(stop_flag, progress_sender, tool_type, fix_names.then(NameFixerParams::default))
}

fn video_optimizer(video_optimizer: VideoOptimizerArgs, stop_flag: &Arc<AtomicBool>, progress_sender: &Sender<ProgressData>, tool_type: &str) -> CliOutput {
    use crate::commands::{CropArgs, TranscodeArgs, VideoOptimizerMode as CliVideoOptimizerMode};

    let VideoOptimizerArgs { common_cli_items, mode } = video_optimizer;

    match mode {
        CliVideoOptimizerMode::Transcode(transcode_args) => {
            let TranscodeArgs {
                excluded_codecs,
                generate_thumbnails,
                thumbnail_percentage,
                thumbnail_grid,
                fix_videos,
                target_codec,
                quality,
                fail_if_not_smaller,
                overwrite_original,
                limit_video_size,
                max_width,
                max_height,
                thumbnail_grid_tiles_per_side,
            } = transcode_args;

            let excluded_codecs_vec = excluded_codecs.map_or_else(
                || vec!["hevc".to_string(), "h265".to_string(), "av1".to_string(), "vp9".to_string()],
                |s| s.split(',').map(|c| c.trim().to_string()).collect(),
            );

            let params = VideoOptimizerParameters::VideoTranscode(VideoTranscodeParams::new(
                excluded_codecs_vec,
                generate_thumbnails,
                thumbnail_percentage,
                thumbnail_grid,
                thumbnail_grid_tiles_per_side,
            ));

            let fix_params = fix_videos.then_some(VideoOptimizerFixParams::VideoTranscode(VideoTranscodeFixParams {
                codec: target_codec,
                quality,
                fail_if_not_smaller,
                overwrite_original,
                limit_video_size,
                max_width,
                max_height,
            }));

            ToolRunner::new(VideoOptimizer::new(params), &common_cli_items)
                .run_with_fix(stop_flag, progress_sender, tool_type, fix_params)
        }
        CliVideoOptimizerMode::Crop(crop_args) => {
            let CropArgs {
                crop_mechanism,
                black_pixel_threshold,
                black_bar_percentage,
                max_samples,
                min_crop_size,
                generate_thumbnails,
                thumbnail_percentage,
                thumbnail_grid,
                thumbnail_grid_tiles_per_side,
                fix_videos,
                overwrite_original,
                target_codec,
                quality,
            } = crop_args;

            #[expect(clippy::match_same_arms)]
            let crop_mech = match crop_mechanism.as_str() {
                "blackbars" => VideoCroppingMechanism::BlackBars,
                "staticcontent" => VideoCroppingMechanism::StaticContent,
                _ => VideoCroppingMechanism::BlackBars,
            };

            let params = VideoOptimizerParameters::VideoCrop(VideoCropParams::with_custom_params(
                crop_mech,
                black_pixel_threshold,
                black_bar_percentage,
                max_samples,
                min_crop_size,
                generate_thumbnails,
                thumbnail_percentage,
                thumbnail_grid,
                thumbnail_grid_tiles_per_side,
            ));

            let fix_params = fix_videos.then_some(VideoOptimizerFixParams::VideoCrop(VideoCropFixParams {
                overwrite_original,
                target_codec,
                quality,
                crop_mechanism: crop_mech,
            }));

            ToolRunner::new(VideoOptimizer::new(params), &common_cli_items)
                .run_with_fix(stop_flag, progress_sender, tool_type, fix_params)
        }
    }
}

fn exif_remover(exif_remover: ExifRemoverArgs, stop_flag: &Arc<AtomicBool>, progress_sender: &Sender<ProgressData>, tool_type: &str) -> CliOutput {
    let ExifRemoverArgs {
        common_cli_items,
        ignored_tags,
        fix_exif,
        override_file,
    } = exif_remover;

    let ignored_tags_vec = ignored_tags.map(|s| s.split(',').map(|tag| tag.trim().to_string()).collect()).unwrap_or_default();
    let params = ExifRemoverParameters::new(ignored_tags_vec);

    ToolRunner::new(ExifRemover::new(params), &common_cli_items)
        .run_with_fix(stop_flag, progress_sender, tool_type, fix_exif.then_some(ExifTagsFixerParams { override_file }))
}

fn save_and_write_results_to_writer<T: CommonData + PrintResults>(component: &T, common_cli_items: &CommonCliItems, tool_type: &str) -> CliOutput {
    let mut had_save_errors = false;

    match common_cli_items.file_to_save.file_name() {
        Some(file_name) => {
            if let Err(e) = component.print_results_to_file(file_name) {
                error!("Failed to save results to file {e}");
                had_save_errors = true;
            }
        }
        None if common_cli_items.file_to_save.is_specified() => {
            had_save_errors = true;
        }
        None => {}
    }
    match common_cli_items.json_compact_file_to_save.file_name() {
        Some(file_name) => {
            if let Err(e) = component.save_results_to_file_as_json(file_name, false) {
                error!("Failed to save compact json results to file {e}");
                had_save_errors = true;
            }
        }
        None if common_cli_items.json_compact_file_to_save.is_specified() => {
            had_save_errors = true;
        }
        None => {}
    }
    match common_cli_items.json_pretty_file_to_save.file_name() {
        Some(file_name) => {
            if let Err(e) = component.save_results_to_file_as_json(file_name, true) {
                error!("Failed to save pretty json results to file {e}");
                had_save_errors = true;
            }
        }
        None if common_cli_items.json_pretty_file_to_save.is_specified() => {
            had_save_errors = true;
        }
        None => {}
    }

    // --json-compact-stdout: write a stable JSON envelope to stdout
    if common_cli_items.json_compact_stdout {
        let messages = component.get_text_messages();
        let mut msg_list: Vec<String> = Vec::new();
        for w in &messages.warnings {
            msg_list.push(format!("[warning] {w}"));
        }
        for e in &messages.errors {
            msg_list.push(format!("[error] {e}"));
        }
        for m in &messages.messages {
            msg_list.push(m.clone());
        }

        // Serialize results via temp file, then read back as raw JSON value
        let results_json = match write_results_json_to_buffer(component) {
            Ok(buf) => {
                serde_json::from_slice::<serde_json::Value>(&buf).unwrap_or(serde_json::Value::Null)
            }
            Err(e) => {
                error!("Failed to serialize results for stdout envelope: {e}");
                had_save_errors = true;
                serde_json::Value::Null
            }
        };

        let envelope = serde_json::json!({
            "schema_version": 1,
            "tool_type": tool_type,
            "results": results_json,
            "messages": msg_list,
        });

        if let Err(e) = serde_json::to_writer(std::io::stdout().lock(), &envelope) {
            error!("Failed to write JSON envelope to stdout: {e}");
            had_save_errors = true;
        }
        println!(); // trailing newline
    }

    let mut buf_writer = std::io::BufWriter::new(Vec::new());
    if !common_cli_items.do_not_print.do_not_print_results {
        if let Err(e) = component.print_results_to_writer(&mut buf_writer) {
            error!("Failed to print results to output: {e}");
            had_save_errors = true;
        }
    }

    if !common_cli_items.do_not_print.do_not_print_messages {
        if let Err(e) = component.get_text_messages().print_messages_to_writer(&mut buf_writer) {
            error!("Failed to print results to output: {e}");
            had_save_errors = true;
        }
    }

    let mut cli_output = CliOutput {
        found_any_files: component.found_any_items(),
        ignored_error_code_on_found: common_cli_items.ignore_error_code_on_found,
        had_save_errors,
        output: String::new(),
    };

    if let Ok(file_vec) = buf_writer.into_inner()
        && let Ok(output) = String::from_utf8(file_vec)
    {
        cli_output.output = output;
    }

    cli_output
}

fn write_results_json_to_buffer<T: PrintResults>(component: &T) -> std::io::Result<Vec<u8>> {
    use std::io::Read;
    let tmp = tempfile::NamedTempFile::new()?;
    let path = tmp.path().to_string_lossy().to_string();
    component.save_results_to_file_as_json(&path, false)?;
    let mut buf = Vec::new();
    std::fs::File::open(&path)?.read_to_end(&mut buf)?;
    Ok(buf)
}

fn set_simple_delete<T>(component: &mut T, s_delete: SDMethod)
where
    T: AllTraits,
{
    if s_delete.delete_files {
        component.set_delete_method(DeleteMethod::Delete);
    }
    component.set_dry_run(s_delete.dry_run);
    component.set_move_to_trash(s_delete.move_to_trash);
}

fn set_advanced_delete<T>(component: &mut T, a_delete: DMethod)
where
    T: AllTraits,
{
    component.set_delete_method(a_delete.delete_method);
    component.set_dry_run(a_delete.dry_run);
    component.set_move_to_trash(a_delete.move_to_trash);
}

fn set_common_settings<T>(component: &mut T, common_cli_items: &CommonCliItems, reference_directories: Option<&Vec<PathBuf>>)
where
    T: AllTraits,
{
    set_number_of_threads(common_cli_items.thread_number);

    let mut included_directories = common_cli_items.directories.clone();
    if let Some(reference_directories) = reference_directories {
        included_directories.extend_from_slice(reference_directories);
        component.set_reference_paths(reference_directories.clone());
    }

    component.set_included_paths(included_directories);
    component.set_excluded_paths(common_cli_items.excluded_directories.clone());
    component.set_excluded_items(common_cli_items.excluded_items.clone());
    component.set_recursive_search(!common_cli_items.not_recursive);
    #[cfg(target_family = "unix")]
    component.set_exclude_other_filesystems(common_cli_items.exclude_other_filesystems);
    component.set_allowed_extensions(common_cli_items.allowed_extensions.clone());
    component.set_excluded_extensions(common_cli_items.excluded_extensions.clone());
    component.set_use_cache(!common_cli_items.disable_cache);
}

fn similar_documents(args: SimilarDocumentsArgs, stop_flag: &Arc<AtomicBool>, progress_sender: &Sender<ProgressData>, tool_type: &str) -> CliOutput {
    let SimilarDocumentsArgs {
        common_cli_items,
        delete_method,
        minimal_file_size,
        maximal_file_size,
        similarity_threshold,
        num_hashes,
        shingle_size,
    } = args;

    let params = SimilarDocumentsParameters::new(similarity_threshold, num_hashes, shingle_size);

    ToolRunner::new(SimilarDocuments::new(params), &common_cli_items)
        .configure(|tool| {
            tool.set_minimal_file_size(minimal_file_size);
            tool.set_maximal_file_size(maximal_file_size);
            set_advanced_delete(tool, delete_method);
        })
        .run(stop_flag, progress_sender, tool_type)
}
