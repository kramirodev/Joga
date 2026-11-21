import { useRef, useState } from 'react';
import { View } from 'react-native';

import type { Sport } from '../api/types';
import { BottomSheetFrame, useSheetClose } from './BottomSheetFrame';
import { Btn, BtnRow, Chip, ChipRow, Field, TextBtn, Txt } from './kit';
import {
  DEFAULT_VENUE_FILTERS,
  VENUE_DISTANCE_OPTIONS,
  formatOptions,
  isDefaultFilters,
  type VenueCoverage,
  type VenueFilters,
} from './venueFilters';

const COVERAGE_OPTIONS: { value: VenueCoverage; label: string }[] = [
  { value: 'any', label: 'Tanto faz' },
  { value: 'covered', label: 'Coberta' },
  { value: 'open', label: 'Aberta' },
];

function withRegion(filters: VenueFilters, regionDefined: boolean): VenueFilters {
  return regionDefined || filters.maxKm == null ? filters : { ...filters, maxKm: null };
}

function VenueFilterFooter({
  draft,
  regionDefined,
  onApply,
}: {
  draft: VenueFilters;
  regionDefined: boolean;
  onApply: (filters: VenueFilters) => void;
}) {
  const close = useSheetClose();
  const applying = useRef(false);
  return (
    <BtnRow>
      <Btn tone="ghost" onPress={() => close()}>
        Voltar
      </Btn>
      <Btn
        tone="primary"
        onPress={() => {
          if (applying.current) {
            return;
          }
          applying.current = true;
          close(() => onApply(withRegion(draft, regionDefined)));
        }}
      >
        Aplicar filtros
      </Btn>
    </BtnRow>
  );
}

export function VenueFilterSheet({
  visible,
  filters,
  catalog,
  catalogLoading,
  catalogFailed,
  regionDefined,
  onApply,
  onClose,
  onRetryCatalog,
  onOpenRegion,
}: {
  visible: boolean;
  filters: VenueFilters;
  catalog: Sport[];
  catalogLoading: boolean;
  catalogFailed: boolean;
  regionDefined: boolean;
  onApply: (filters: VenueFilters) => void;
  onClose: () => void;
  onRetryCatalog: () => void;
  onOpenRegion: () => void;
}) {
  // Remonta ao abrir: o rascunho sempre nasce do estado comprometido.
  return (
    <VenueFilterForm
      key={visible ? 'open' : 'closed'}
      visible={visible}
      filters={filters}
      catalog={catalog}
      catalogLoading={catalogLoading}
      catalogFailed={catalogFailed}
      regionDefined={regionDefined}
      onApply={onApply}
      onClose={onClose}
      onRetryCatalog={onRetryCatalog}
      onOpenRegion={onOpenRegion}
    />
  );
}

function VenueFilterForm({
  visible,
  filters,
  catalog,
  catalogLoading,
  catalogFailed,
  regionDefined,
  onApply,
  onClose,
  onRetryCatalog,
  onOpenRegion,
}: {
  visible: boolean;
  filters: VenueFilters;
  catalog: Sport[];
  catalogLoading: boolean;
  catalogFailed: boolean;
  regionDefined: boolean;
  onApply: (filters: VenueFilters) => void;
  onClose: () => void;
  onRetryCatalog: () => void;
  onOpenRegion: () => void;
}) {
  const close = useSheetClose();
  const [draft, setDraft] = useState<VenueFilters>(() => withRegion(filters, regionDefined));
  const options = formatOptions(catalog);
  const normalized = withRegion(draft, regionDefined);

  return (
    <BottomSheetFrame
      visible={visible}
      onClose={onClose}
      title="Filtrar quadras"
      subtitle="Filtros são preferências, nunca anúncios."
      accessibilityLabel="Filtrar quadras"
      footer={<VenueFilterFooter draft={draft} regionDefined={regionDefined} onApply={onApply} />}
    >
      <View style={{ gap: 16 }}>
        <Field label="Esporte">
          {catalogFailed ? (
            <View style={{ gap: 4 }}>
              <Txt variant="tiny">Não foi possível carregar os esportes.</Txt>
              <TextBtn onPress={onRetryCatalog}>Tentar de novo</TextBtn>
            </View>
          ) : catalogLoading ? (
            <Txt variant="tiny">Carregando esportes…</Txt>
          ) : options.length === 0 ? (
            <Txt variant="tiny">Nenhum esporte disponível.</Txt>
          ) : (
            <ChipRow>
              <Chip
                on={!draft.formatId}
                onPress={() => setDraft((current) => ({ ...current, formatId: null }))}
              >
                Todos
              </Chip>
              {options.map((option) => (
                <Chip
                  key={option.id}
                  on={draft.formatId === option.id}
                  onPress={() => setDraft((current) => ({ ...current, formatId: option.id }))}
                  accessibilityLabel={`Filtrar por ${option.label}`}
                >
                  {option.label}
                </Chip>
              ))}
            </ChipRow>
          )}
        </Field>
        <Field label="Cobertura">
          <ChipRow>
            {COVERAGE_OPTIONS.map((option) => (
              <Chip
                key={option.value}
                on={draft.coverage === option.value}
                onPress={() => setDraft((current) => ({ ...current, coverage: option.value }))}
              >
                {option.label}
              </Chip>
            ))}
          </ChipRow>
        </Field>
        <Field label="Distância">
          <ChipRow>
            <Chip
              on={normalized.maxKm == null}
              disabled={!regionDefined}
              onPress={() => setDraft((current) => ({ ...current, maxKm: null }))}
            >
              Qualquer
            </Chip>
            {VENUE_DISTANCE_OPTIONS.map((distance) => (
              <Chip
                key={distance}
                on={normalized.maxKm === distance}
                disabled={!regionDefined}
                onPress={() => setDraft((current) => ({ ...current, maxKm: distance }))}
              >
                {`${distance} km`}
              </Chip>
            ))}
          </ChipRow>
          {regionDefined ? (
            <Txt variant="tiny">A distância é medida a partir da sua região salva.</Txt>
          ) : (
            <View style={{ gap: 4 }}>
              <Txt variant="tiny">Defina sua região para filtrar por distância.</Txt>
              <TextBtn onPress={() => close(onOpenRegion)}>Definir região</TextBtn>
            </View>
          )}
        </Field>
        <TextBtn
          muted
          onPress={() => setDraft(DEFAULT_VENUE_FILTERS)}
          disabled={isDefaultFilters(normalized)}
        >
          Limpar seleção
        </TextBtn>
      </View>
    </BottomSheetFrame>
  );
}
