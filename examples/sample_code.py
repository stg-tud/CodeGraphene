# Snippet from RepoCoder function_level_completion_4k_context_codex dataset.
# https://github.com/microsoft/CodeT/blob/main/RepoCoder/datasets/datasets.zip

if self._count % self.gas == 0:
            self.optimizer_step()

            # param callback (e.g., parameter clipping)
            if self.is_implemented("param_callback"):
                self.param_callback()

            if self._strategy != "default" and self._count % (self.gas * 20) == 0:
                self.synchronize_params(self.trainable_parameters())

            # zero-out grad
            self.zero_grad()

        return loss_dict

    def step_normal(self, global_step=None):
        if self.check_ready():
            # loop start
            if self._inner_loop_start:
                if self.is_implemented("on_inner_loop_start"):
                    self.on_inner_loop_start()
                self._inner_loop_start = False

                # copy current parameters, buffers, optimizer states
                if self._roll_back:
                    self.cache_states()

            # increase count (local step)
            if self._training:
                self._count += 1

            # one step grdient descent
            loss_dict = self.one_step_descent()

            # lr scheduler step
            if self.scheduler is not None and not self._roll_back:
                self.scheduler.step()

            # logging
            if (
                self.log_step > 0
                and self._count % self.log_step == 0
                and self.is_rank_zero()
            ):
                self.log(loss_dict, global_step)

            # call parent step_normal after unrolling
            if (
                self._training
                and self._count % (self._unroll_steps * self.gas) == 0
                and self._count > self.warmup_steps
            ):
                for problem in self._parents:
                    idx = problem.children.index(self)
                    problem.ready[idx] = True
                    problem.step_normal(global_step=global_step)

                self._inner_loop_start = True

            self.ready = [False for _ in range(len(self._children))]

    def step_after_roll_back(self):
        if self.check_ready() and self._training:
            if self._roll_back:
                # recover from cached states
                self.recover_states()

                # one step gradient step
                _ = self.one_step_descent(batch=self.cur_batch)

                # lr scheduler
                if self.scheduler is not None:
                    self.scheduler.step()

                # call parent step_after_roll_back
                for problem in self._parents:
                    idx = problem.children.index(self)
                    problem.ready[idx] = True
                    problem.step_after_roll_back()

            self.ready = [False for _ in range(len(self._children))]

    def step(self, global_step=None):
        """
        ``step`` method abstracts a one-step gradient descent update with four sub-steps:
        1) data loading, 2) cost calculation, 3) gradient calculation, and 4) parameter update.
        It also calls upper-level problems' step methods after unrolling gradient steps based on
        the hierarchical dependency graph.

        :param global_step: global step of the whole multilevel optimization. Defaults to None.
        :type global_step: int, optional
        """
        self._global_step = global_step
        self.step_normal(global_step=global_step)
        if (
            self._count % (self._unroll_steps * self.gas) == 0
            and self._count > self.warmup_steps
        ):
            self.step_after_roll_back()

    def get_batch(self):
        """
        Load training batch from the user-provided data loader

        :return: New training batch
        :rtype: Any
        """
        batch = tuple(
            self.get_batch_single_loader(i) for i in range(len(self.train_data_loader))
        )

        return batch[0] if len(batch) == 1 else batch

    def get_batch_single_loader(self, idx):
        """
        Load training batch from one of the user-provided data loader(s)

        :return: New training batch
        :rtype: Any
        """
        data_iterator = self.train_data_iterator[idx]
        try:
            batch = next(data_iterator)
        except StopIteration:
            if idx == 0:
                self.epoch_callback_exec()
            self.epoch_counter[idx] += 1
            train_data_loader = self.train_data_loader[idx]
            if self._strategy in ["distributed", "zero", "fsdp"]:
                train_data_loader.set_epoch(self.epoch_counter[idx])
            self.train_data_iterator[idx] = iter(train_data_loader)
            batch = next(self.train_data_iterator[idx])
        if not isinstance(batch, dict):
            batch = tuple(
                convert_tensor(value, self.device, self._is_default_fp16())
                for value in batch
            )
        else:
            for key, value in batch.items():
                batch[key] = convert_tensor(value, self.device, self._is_default_fp16())

        return batch

    def get_loss(self, batch):
        """
        Calculate loss and log metrics for the current batch based on the user-defined loss
        function.

        :return: loss and log metrics (e.g. classification accuracy)
        :rtype: dict
        """
        maybe_loss_dict = self.training_step_exec(batch)
        is_dict = isinstance(maybe_loss_dict, dict)
        loss = maybe_loss_dict["loss"] if is_dict else maybe_loss_dict
        loss_no_scale = loss.item()
        if self._is_default_fp16():
            loss = self.scaler.scale(loss)
        loss = loss / self.gas

        # construct loss dict
        loss_dict = {"loss": loss_no_scale}
        if is_dict:
            for key, value in maybe_loss_dict.items():
                if key != "loss":
                    loss_dict[key] = value

        return loss, loss_dict

    def backward(
        self,
        loss,
        params,
        paths,
        create_graph=False,
        retain_graph=True,
        allow_unused=True,
    ):
        """
        Calculate the gradient of ``loss`` with respect to ``params`` based on a user-defined
        ``config``.

        :param loss: Outputs of the differentiated function.
        :type loss: Tensor
        :param params: Inputs with respect to which the gradient will be returned.
        :type params: Sequence of Tensor
        :param paths: Paths on which the gradient will be calculated.
        :type paths: List of list of Problem
        :param create_graph:
            If ``True``, graph of the derivative will be constructed, allowing to compute higher order
            derivative products. Default: ``True``.
        :type create_graph: bool, optional
        :param retain_graph:
            If ``False``, the graph used to compute the grad will be freed. Note that in nearly all
            cases setting this option to ``True`` is not needed and often can be worked around in a much
            more efficient way. Defaults to the value of ``create_graph``.
        :type retain_graph: bool, optional
        :param allow_unused:
            If ``False``, specifying inputs that were not used when computing outputs (and therefore
            their grad is always zero) is an error. Defaults to ``False``.
        :type allow_unused: bool, optional
        """
        # direct grad
        if len(paths) > 0 or not self.gradient_accumulation_boundary():
            grads = torch.autograd.grad(
                loss,
                params,
                create_graph=create_graph,
                retain_graph=retain_graph,
                allow_unused=allow_unused,
            )
            self.set_grads(params, grads)
        else:
            torch.autograd.backward(
                loss,
                inputs=params,
                create_graph=create_graph,
                retain_graph=retain_graph,
            )

        # indirect grad: best-response Jacobian
        if self._config.first_order:
            for idx, path in enumerate(paths):
                retain_graph_implicit = False if idx == len(paths) - 1 else True
                do_sync = bool(
                    idx == len(paths) - 1 and self.gradient_accumulation_boundary()
                )
                grads = get_grads(loss, path, retain_graph_implicit, do_sync)
                if not do_sync:
                    self.set_grads(params, grads)

    def set_grads(self, params, grads):
        """
        Set gradients for trainable parameters. ``params.grad = grads``

        :param params: Trainable parameters
        :type params: Sequence of Tensor
        :param grads: Calculated gradient
        :type grads: Sequence of Tensor
        """
        for param, grad in zip(params, grads):
            if grad is not None:
                if hasattr(param, "grad") and param.grad is not None:
                    param.grad = param.grad + grad
                else:
                    param.grad = grad

    def synchronize_params(self, params):
        """
        synchronize parameters across distributed data-parallel processes
        """
        if self._world_size > 1 and self._strategy not in ["fsdp", "accelerate"]:
            for param in params:
                dist.broadcast(param.data, 0)

    @abc.abstractmethod
    def optimizer_step(self, *args, **kwargs):
        """
        Update weights as in PyTorch's native ``optim.step()``
        """
        raise NotImplementedError

    def zero_grad(self):
        """
        Set gradients for trainable parameters for the current problem to 0.
        Similar with PyTorch's ``optim.zero_grad()`` or ``module.zero_grad()``.
        """
        for param in list(self.trainable_parameters()):
            if hasattr(param, "grad"):
                del param.grad

    def clip_grad(self):
        """
        Perform gradient clipping based on the norm provided by Config
        """
        if self._strategy != "fsdp":
            torch.nn.utils.clip_grad_norm_(
                parameters=self.trainable_parameters(), max_norm=self.gradient_clipping
            )
        else:
            self.module.clip_grad_norm_(max_norm=self.gradient_clipping)

    def state_dict(self):
        """
        Return all states involved in ``Problem`` with a Python dictionary. By default, it
        includes ``self.module.state_dict`` and ``self.optimizer.state_dict``. Depending on users'
        configurations, it may include ``self.scheuler.state_dict`` (lr scheduler) and
        ``self.scaler.state_dict`` (fp16 training)
        """
        state_dict = {}
        state_dict["module"] = self.module.state_dict()
        state_dict["optimizer"] = self.optimizer.state_dict()
        if self.scheduler is not None:
            state_dict["scheduler"] = self.scheduler.state_dict()
        if self._is_default_fp16():
            state_dict["scaler"] = self.scaler.state_dict()

        return state_dict

    def load_state_dict(self, state_dict):
        """Load the state for the ``Problem``

        Args:
            state_dict (dict): Python dictionary of Problem states.
        """
        self.module.load_state_dict(state_dict["module"])
        self.optimizer.load_state_dict(state_dict["optimizer"])
        if self.scheduler is not None and "scheduler" in state_dict:
            self.scheduler.load_state_dict(state_dict["scheduler"])
        if self._is_default_fp16() and "scaler" in state_dict:
            self.scaler.load_state_dict(state_dict["scaler"])

    def configure_distributed_training(self, dictionary):
        """
        Set the configuration for distributed training.

        :param dictionary: Python dictionary of distributed training provided by Engine.
        :type dictionary: dict
        """
        self._strategy = dictionary["strategy"]
        self._backend = dictionary["backend"]
        self._world_size = dictionary["world_size"]
        self._rank = dictionary["rank"]
        self._local_rank = dictionary["local_rank"]

    def configure_roll_back(self, roll_back):
        """
        Set the roll-back (warm- start) option from Engine

        :param roll_back: roll-back (warm-start) on/off
        :type roll_back: bool
        """
        if len(self._parents) > 0:
            self._roll_back = roll_back

    def configure_device(self, device):
        """
        Set the device for the current problem.
        """
        self.device = device

    def get_opt_param_group_for_param(self, param):
        """
        Get optimizer param_group for specific parameter

        :param param: Parameter for which optimizer param_group is inquired
        :type param: torch.nn.Parameter
        :return: param_group for the given parameter
        :rtype: dict
        """
        param_groups = self.optimizer.param_groups
        for group in param_groups:
            for p in group["params"]:
                if param is p:
                    return group

    def get_opt_state_for_param(self, param):
        """
        Get optimizer state for specific parameter

        :param param: Parameter for which optimizer state is inquired
        :type param: torch.nn.Parameter
        :return: optimizer state for the given parameter
        :rtype: dict
        """
        state = self.optimizer.state
        return state[param]

    @abc.abstractmethod
    def cache_states(self):
        """
        Cache params, buffers, optimizer states when ``config.roll_back`` is set to ``True`` in
        ``step``.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def recover_states(self):
        """
        Recover params, buffers, optimizer states when ``config.roll_back`` is set to ``True`` in
        ``step``.
        """
        raise NotImplementedError

    def epoch_callback_exec(self):
        if self.is_implemented("epoch_callback"):
            self.epoch_callback()

    def gradient_accumulation_boundary(self):
        """
        Check whether the current step is on the gradient accumulation boundary
        """
        return bool(self._count % self.gas == 0)

    def _is_default_fp16(self):
        """
        Check whether to use PyTorch native fp16 (mixed-precision) feature
        """
        if not self._fp16 or self._strategy in ["accelerate"]:
            return False
        return True

    def is_implemented(self, fn_name):
        """
        Check if ``fn_name`` method is implemented in the class

        :rtype: bool
        """
        return callable(getattr(self, fn_name, None))

    def check_ready(self):
        """
        Check if unrolling processes of lower level problems in the hierarchical dependency
        graph are all ready/done. ``step`` function is only excuted when this method returns
        ``True``.

        :rtype: bool
        """
        return all(self.ready)

    def log(self, stats, global_step):
        """
        Log (training) stats to the ``self.logger``

        :param stats: log metrics such as loss and classification accuracy.
        :type stats: Any
        :param step: global/local step associated with the ``stats``.
        :type step: int
        """
