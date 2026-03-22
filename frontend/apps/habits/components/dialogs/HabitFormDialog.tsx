import React, { useEffect } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { X, Calendar, Flag, AlignLeft } from "lucide-react";
import { useForm } from "react-hook-form";
import { HabitListItem, FrequencyType } from "../../types/backend";
import {
  mindspaceApi,
  ValueOption,
  CommitmentOption,
} from "../../apis/mindspace";
import { useHabitStore } from "../../hooks/useHabitStore";
import { useToast } from "../shared/Toast";

interface HabitFormDialogProps {
  isOpen: boolean;
  onClose: () => void;
  habit?: HabitListItem; // If provided, we are in edit mode
}

interface HabitFormData {
  name: string;
  description: string;
  frequencyType: FrequencyType;
  specificDays: number[];
  initialLevel: number;
  valueId: string;
  commitmentId: string;
}

const FREQUENCY_OPTIONS: { label: string; value: FrequencyType }[] = [
  { label: "每天", value: "daily" },
  { label: "工作日", value: "weekdays" },
  { label: "周末", value: "weekend" },
  { label: "自定义", value: "custom" },
];

const WEEK_DAYS = [
  { label: "一", value: 1 },
  { label: "二", value: 2 },
  { label: "三", value: 3 },
  { label: "四", value: 4 },
  { label: "五", value: 5 },
  { label: "六", value: 6 },
  { label: "日", value: 7 },
];

export const HabitFormDialog: React.FC<HabitFormDialogProps> = ({
  isOpen,
  onClose,
  habit,
}) => {
  const { createHabit, updateHabit } = useHabitStore();
  const { showToast } = useToast();
  const isEditMode = !!habit;

  const [values, setValues] = React.useState<ValueOption[]>([]);
  const [commitments, setCommitments] = React.useState<CommitmentOption[]>([]);

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<HabitFormData>({
    defaultValues: {
      name: "",
      description: "",
      frequencyType: "daily",
      specificDays: [],
      initialLevel: 0,
      valueId: "",
      commitmentId: "",
    },
  });

  const frequencyType = watch("frequencyType");
  const specificDays = watch("specificDays");
  const initialLevel = watch("initialLevel");
  const selectedValueId = watch("valueId");

  const availableCommitments = React.useMemo(() => {
    if (!selectedValueId) return commitments;
    return commitments.filter((c) => c.value_id === selectedValueId);
  }, [commitments, selectedValueId]);

  useEffect(() => {
    if (isOpen) {
      mindspaceApi.getValues().then(setValues).catch(console.error);
      mindspaceApi.getCommitments().then(setCommitments).catch(console.error);

      if (habit) {
        reset({
          name: habit.name,
          description: habit.description || "",
          frequencyType: habit.frequency.type,
          specificDays: habit.frequency.specificDays || [],
          initialLevel: habit.currentLevel,
          valueId: habit.valueId || "",
          commitmentId: habit.commitmentId || "",
        });
      } else {
        reset({
          name: "",
          description: "",
          frequencyType: "daily",
          specificDays: [],
          initialLevel: 0,
          valueId: "",
          commitmentId: "",
        });
      }
    }
  }, [isOpen, habit, reset]);

  const onSubmit = async (data: HabitFormData) => {
    const payload = {
      name: data.name,
      description: data.description || null,
      frequency: {
        type: data.frequencyType,
        specificDays:
          data.frequencyType === "custom" ? data.specificDays : undefined,
      },
      valueId: data.valueId || null,
      commitmentId: data.commitmentId || null,
    };

    try {
      if (isEditMode) {
        await updateHabit(habit.id, {
          ...payload,
          level: data.initialLevel,
        });
        showToast("success", "习惯已更新");
      } else {
        await createHabit({
          ...payload,
          initialLevel: data.initialLevel,
        });
        showToast("success", "习惯已创建");
      }
      onClose();
    } catch {
      showToast("error", isEditMode ? "更新失败，请重试" : "创建失败，请重试");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      onClose();
    }
  };

  // calculate preview
  const calculatePreview = (
    level: number,
    type: FrequencyType,
    days: number[],
  ) => {
    const LEVEL_CHALLENGE_WEEKS = [3, 4, 6, 8, 12];
    const weeks = LEVEL_CHALLENGE_WEEKS[level] || 3;
    let weeklyDays = 7;
    if (type === "weekdays") weeklyDays = 5;
    if (type === "weekend") weeklyDays = 2;
    if (type === "custom") weeklyDays = days.length;

    const requiredCompletions = Math.ceil(weeks * weeklyDays * 0.85);
    return `挑战周期：${weeks} 周 | 最低完成：${requiredCompletions} 天`;
  };

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[9999] isolate flex items-center justify-center"
          onKeyDown={handleKeyDown}
        >
          <div
            className="absolute inset-0 z-0 bg-slate-900/40 backdrop-blur-sm"
            onClick={onClose}
          />

          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
            className="relative z-10 w-full max-w-[500px] bg-white rounded-2xl shadow-xl overflow-hidden flex flex-col max-h-[90vh]"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 shrink-0">
              <h2 className="text-lg font-bold text-slate-800">
                {isEditMode ? "编辑习惯" : "新建习惯"}
              </h2>
              <button
                onClick={onClose}
                className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            {/* Form Body */}
            <form
              id="habit-form"
              onSubmit={handleSubmit(onSubmit)}
              className="overflow-y-auto px-6 py-5 flex-1 space-y-5"
            >
              {/* Warning if editing frequency/level */}
              {isEditMode &&
                (habit.currentLevel !== initialLevel ||
                  habit.frequency.type !== frequencyType ||
                  (habit.frequency.specificDays || []).join(",") !==
                    (specificDays || []).join(",")) && (
                  <div className="bg-amber-50 border border-amber-200 text-amber-700 text-sm px-4 py-3 rounded-xl mb-4">
                    修改等级或频率将重置当前挑战进度，确认继续？
                  </div>
                )}

              {/* Name */}
              <div className="space-y-1.5">
                <label className="text-sm font-semibold text-slate-700 block">
                  习惯名称
                </label>
                <input
                  {...register("name", { required: "请输入习惯名称" })}
                  className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 text-slate-700"
                  placeholder="例如：早起、冥想、跑步"
                />
                {errors.name && (
                  <p className="text-xs text-red-500 mt-1">
                    {errors.name.message}
                  </p>
                )}
              </div>

              {/* Frequency */}
              <div className="space-y-3">
                <label className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <Calendar size={16} className="text-indigo-500" />
                  频率
                </label>
                <div className="flex bg-slate-100 p-1 rounded-xl">
                  {FREQUENCY_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setValue("frequencyType", opt.value)}
                      className={`flex-1 py-1.5 px-2 rounded-lg text-sm font-medium transition-all ${
                        frequencyType === opt.value
                          ? "bg-white text-indigo-600 shadow-sm"
                          : "text-slate-500 hover:text-slate-700"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>

                {/* Custom Days Selection */}
                <AnimatePresence>
                  {frequencyType === "custom" && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="flex justify-between gap-1 pt-2">
                        {WEEK_DAYS.map((day) => {
                          const isSelected = specificDays.includes(day.value);
                          return (
                            <button
                              key={day.value}
                              type="button"
                              onClick={() => {
                                const newDays = isSelected
                                  ? specificDays.filter((d) => d !== day.value)
                                  : [...specificDays, day.value].sort(
                                      (a, b) => a - b,
                                    );
                                setValue("specificDays", newDays);
                              }}
                              className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium transition-all shadow-sm ${
                                isSelected
                                  ? "bg-indigo-500 text-white shadow-indigo-500/20"
                                  : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
                              }`}
                            >
                              {day.label}
                            </button>
                          );
                        })}
                      </div>
                      {frequencyType === "custom" &&
                        specificDays.length === 0 && (
                          <p className="text-xs text-red-500 mt-2">
                            请至少选择一天
                          </p>
                        )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Level */}
              <div className="space-y-3">
                <label className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <Flag size={16} className="text-emerald-500" />
                  挑战等级
                </label>
                <div className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 flex items-center justify-between">
                  <span className="text-sm text-slate-600 font-medium">
                    设定起始等级
                  </span>
                  <div className="flex gap-1.5">
                    {[0, 1, 2, 3, 4].map((level) => (
                      <button
                        key={level}
                        type="button"
                        onClick={() => setValue("initialLevel", level)}
                        className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold transition-all ${
                          initialLevel === level
                            ? "bg-emerald-500 text-white shadow-md shadow-emerald-500/20"
                            : "bg-white text-slate-500 border border-slate-200 hover:border-emerald-300 hover:text-emerald-600"
                        }`}
                      >
                        {level}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Value and Commitment */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                    关联价值
                  </label>
                  <select
                    {...register("valueId", {
                      onChange: (e) => {
                        const newVId = e.target.value;
                        const currentCommitmentId = watch("commitmentId");
                        if (newVId && currentCommitmentId) {
                          const currentC = commitments.find(
                            (c) => c.id === currentCommitmentId,
                          );
                          if (currentC && currentC.value_id !== newVId) {
                            setValue("commitmentId", "");
                          }
                        }
                      },
                    })}
                    className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 text-slate-700 text-sm"
                  >
                    <option value="">-- 不关联 --</option>
                    {values.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.keywords}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                    关联承诺
                  </label>
                  <select
                    {...register("commitmentId", {
                      onChange: (e) => {
                        const newCId = e.target.value;
                        if (newCId) {
                          const currentC = commitments.find(
                            (c) => c.id === newCId,
                          );
                          if (currentC && currentC.value_id) {
                            setValue("valueId", currentC.value_id);
                          }
                        }
                      },
                    })}
                    className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 text-slate-700 text-sm"
                  >
                    <option value="">-- 不关联 --</option>
                    {availableCommitments.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.content}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Description */}
              <div className="space-y-1.5">
                <label className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <AlignLeft size={16} className="text-slate-400" />
                  习惯描述 (可选)
                </label>
                <textarea
                  {...register("description")}
                  className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-400 text-slate-700 min-h-[80px] resize-none text-sm"
                  placeholder="写下你想培养这个习惯的原因..."
                />
              </div>
            </form>

            {/* Footer */}
            <div className="px-6 py-4 bg-slate-50/80 border-t border-slate-100 shrink-0">
              {/* Preview */}
              <div className="mb-4 flex items-center justify-between px-3 py-2 bg-indigo-50/50 rounded-lg border border-indigo-100/50">
                <span className="text-xs font-medium text-indigo-800">
                  挑战预览
                </span>
                <span className="text-xs text-indigo-600 font-mono">
                  {calculatePreview(initialLevel, frequencyType, specificDays)}
                </span>
              </div>

              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-5 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-200 bg-slate-100 rounded-xl transition-colors"
                >
                  取消
                </button>
                <button
                  type="submit"
                  form="habit-form"
                  disabled={
                    frequencyType === "custom" && specificDays.length === 0
                  }
                  className="px-6 py-2.5 text-sm font-semibold text-white bg-indigo-500 hover:bg-indigo-600 rounded-xl transition-all shadow-md shadow-indigo-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isEditMode ? "保存修改" : "创建习惯"}
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
};
