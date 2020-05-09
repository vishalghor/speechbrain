import logging
from speechbrain.utils.edit_distance import wer_summary

logger = logging.getLogger(__name__)


class TrainLogger:
    """Abstract class defining an interface for training loggers."""

    def log_stats(
        self,
        epoch_stats,
        train_stats=None,
        valid_stats=None,
        test_stats=None,
        verbose=False,
    ):
        """Log the stats for one epoch.

        Arguments
        ---------
        epoch_stats : dict of str:scalar pairs
            Stats relevant to the epoch (e.g. count, learning-rate, etc.)
        train_stats : dict of str:list pairs
            Each loss type is represented with a str : list pair including
            all the values for the training pass.
        valid_stats : dict of str:list pairs
            Each loss type is represented with a str : list pair including
            all the values for the validation pass.
        test_stats : dict of str:list pairs
            Each loss type is represented with a str : list pair including
            all the values for the test pass.
        verbose : bool
            Whether to also put logging information to the standard logger.
        """
        raise NotImplementedError


class FileTrainLogger(TrainLogger):
    """Text logger of training information

    Arguments
    ---------
    save_file : str
        The file to use for logging train information.
    summary_fns : dict of str:function pairs
        Each summary function should take a list produced as output
        from a training/validation pass and summarize it to a single scalar.
    """

    def __init__(self, save_file, summary_fns):
        self.save_file = save_file
        self.summary_fns = summary_fns

    def _item_to_string(self, key, value):
        """Convert one item to string, handling floats"""
        if isinstance(value, float):
            value = f"{value:.2f}"
        return f"{key}: {value}"

    def _stats_to_string(self, stats):
        """Convert all stats to a single string summary"""
        return " - ".join(
            [self._item_to_string(k, v) for k, v in stats.items()]
        )

    def log_stats(
        self,
        epoch_stats,
        train_stats=None,
        valid_stats=None,
        test_stats=None,
        verbose=True,
    ):
        """See TrainLogger.log_epoch()"""
        string_summary = self._stats_to_string(epoch_stats)
        for stats in [train_stats, valid_stats, test_stats]:
            if stats is None:
                continue
            summary = {}
            for stat, value_list in stats.items():
                summary[stat] = self.summary_fns[stat](value_list)
            string_summary += " - " + self._stats_to_string(summary)

        with open(self.save_file, "a") as fout:
            print(string_summary, file=fout)
        if verbose:
            logger.info(string_summary)


class TensorboardLogger(TrainLogger):
    """Logs training information in the format required by Tensorboard.

    Arguments
    ---------
    save_dir : str
        A directory for storing all the relevant logs

    Raises
    ------
    ImportError if Tensorboard is not installed.
    """

    def __init__(self, save_dir):
        self.save_dir = save_dir

        # Raises ImportError if TensorBoard is not installed
        from torch.utils.tensorboard import SummaryWriter

        self.writer = SummaryWriter(self.save_dir)
        self.global_step = {"train": {}, "valid": {}, "epoch": 0}

    def log_stats(
        self,
        epoch_stats,
        train_stats=None,
        valid_stats=None,
        test_stats=None,
        verbose=False,
    ):
        """See TrainLogger.log_epoch()"""
        self.global_step["epoch"] += 1
        for name, value in epoch_stats.items():
            self.writer.add_scalar(name, value, self.global_step["epoch"])

        for dataset, stats in [
            ("train", train_stats),
            ("valid", valid_stats),
            ("test", test_stats),
        ]:
            if stats is None:
                continue
            for stat, value_list in stats.items():
                if stat not in self.global_step[dataset]:
                    self.global_step[dataset][stat] = 0
                tag = f"{stat}/{dataset}"
                for value in value_list:
                    new_global_step = self.global_step[dataset][stat] + 1
                    self.writer.add_scalar(tag, value, new_global_step)
                    self.global_step[dataset][stat] = new_global_step


def summarize_average(stat_list):
    return float(sum(stat_list) / len(stat_list))


def summarize_error_rate(stat_list):
    summary = wer_summary(stat_list)
    return summary["WER"]
