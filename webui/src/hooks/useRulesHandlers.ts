import { useCallback } from 'react';
import { addRule, applyRuleSuggestion, deleteRule, getRuleSuggestions, updateRule } from '../api';
import type { RuleSuggestion, RulesData } from '../types';

export function useRulesHandlers(
  setRules: (data: RulesData) => void,
  setToast: (msg: string) => void,
) {
  const handleAddRule = useCallback(async (ruleType: string, category: string, value: string) => {
    const result = await addRule(ruleType, category, value);
    setRules(result);
    if (!result.error) setToast(`'${value}' 규칙을 추가했습니다.`);
  }, []);

  const handleUpdateRule = useCallback(
    async (oldKey: string, oldValue: string, ruleType: string, category: string, value: string) => {
      const result = await updateRule(oldKey, oldValue, ruleType, category, value);
      setRules(result);
      if (!result.error) setToast(`규칙을 수정했습니다.`);
    },
    [],
  );

  const handleDeleteRule = useCallback(async (key: string, value: string) => {
    setRules(await deleteRule(key, value));
    setToast(`'${value}' 규칙을 삭제했습니다.`);
  }, []);

  const handleGetRuleSuggestions = useCallback(async (): Promise<RuleSuggestion[]> => {
    return getRuleSuggestions();
  }, []);

  const handleApplyRuleSuggestion = useCallback(async (target: string, category: string) => {
    const result = await applyRuleSuggestion(target, category);
    setRules(result);
    if (!result.error) setToast(`'${target}' 규칙을 추가했습니다.`);
    return result;
  }, []);

  return {
    handleAddRule,
    handleUpdateRule,
    handleDeleteRule,
    handleGetRuleSuggestions,
    handleApplyRuleSuggestion,
  };
}
