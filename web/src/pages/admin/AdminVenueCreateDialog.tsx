import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { ErrorNotice } from "../../components/Feedback";
import { CheckboxField, TextField } from "../../components/ui/Field";
import { SearchIcon } from "../../components/ui/Icons";
import { Modal } from "../../components/ui/Modal";
import { adminErrorMessage } from "../../lib/admin";
import { ApiError, api } from "../../lib/api";
import { formatCep, normalizeCep } from "../../lib/cep";
import { requestIdOf } from "../../lib/format";
import { coordinateError, digitsOnly, normalizeWhitespace, textError } from "../../lib/validation";
import type { AdminVenue, AdminPublicVenueCreatePayload } from "../../types";

interface Draft {
  name: string;
  city: string;
  state: string;
  postal_code: string;
  address_line: string;
  latitude: string;
  longitude: string;
  is_public: boolean;
  reason: string;
}

function emptyDraft(): Draft {
  return {
    name: "",
    city: "",
    state: "",
    postal_code: "",
    address_line: "",
    latitude: "",
    longitude: "",
    is_public: true,
    reason: "",
  };
}

function coordinateValue(value: string): number {
  return Number(value.replace(",", "."));
}

function createErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 404) {
    return "A organização da plataforma não foi encontrada. Fale com o suporte.";
  }
  return adminErrorMessage(error);
}

export function AdminVenueCreateDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (venue: AdminVenue) => void;
}) {
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [cepMessage, setCepMessage] = useState<string | null>(null);

  const lookupMutation = useMutation({
    mutationFn: () => api.lookupPostalCode(digitsOnly(draft.postal_code)),
    onSuccess: (result) => {
      setDraft((current) => ({
        ...current,
        postal_code: result.postal_code,
        city: result.city || current.city,
        state: result.state || current.state,
        address_line: result.street || current.address_line,
        latitude:
          result.latitude !== null && result.latitude !== undefined
            ? String(result.latitude)
            : current.latitude,
        longitude:
          result.longitude !== null && result.longitude !== undefined
            ? String(result.longitude)
            : current.longitude,
      }));
      setCepMessage(
        result.latitude === null || result.longitude === null
          ? "CEP localizado sem coordenadas. Informe latitude e longitude manualmente."
          : "CEP localizado e coordenadas preenchidas. Confira o ponto antes de salvar.",
      );
    },
  });

  const createMutation = useMutation({
    mutationFn: (payload: AdminPublicVenueCreatePayload) => api.createAdminVenue(payload),
    onSuccess: (venue) => {
      setDraft(emptyDraft());
      setErrors({});
      setCepMessage(null);
      lookupMutation.reset();
      onCreated(venue);
    },
  });

  function update(patch: Partial<Draft>) {
    setDraft((current) => ({ ...current, ...patch }));
    setErrors({});
  }

  function close() {
    if (createMutation.isPending) return;
    setDraft(emptyDraft());
    setErrors({});
    setCepMessage(null);
    lookupMutation.reset();
    createMutation.reset();
    onClose();
  }

  function lookupCep() {
    const cep = digitsOnly(draft.postal_code);
    if (cep.length !== 8) {
      setErrors((current) => ({
        ...current,
        "venue-create-postal-code": "CEP inválido. Informe os oito dígitos.",
      }));
      document.getElementById("venue-create-postal-code")?.focus();
      return;
    }
    setErrors((current) => ({ ...current, "venue-create-postal-code": "" }));
    setCepMessage(null);
    lookupMutation.mutate();
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (createMutation.isPending) return;
    const next: Record<string, string> = {};
    const nameError = textError(draft.name, {
      label: "o nome da quadra",
      min: 2,
      max: 120,
    });
    if (nameError) next["venue-create-name"] = nameError;
    const cityError = textError(draft.city, { label: "a cidade", min: 2, max: 120 });
    if (cityError) next["venue-create-city"] = cityError;
    if (!/^[A-Za-z]{2}$/.test(draft.state.trim())) {
      next["venue-create-state"] = "Informe a UF com duas letras.";
    }
    const addressError = textError(draft.address_line, {
      label: "o endereço",
      min: 5,
      max: 200,
    });
    if (addressError) next["venue-create-address"] = addressError;
    const postalCode = digitsOnly(draft.postal_code);
    if (postalCode && postalCode.length !== 8) {
      next["venue-create-postal-code"] = "CEP inválido. Informe os oito dígitos.";
    }
    const coordinates = coordinateError(draft.latitude, draft.longitude);
    if (coordinates.latitude) next["venue-create-latitude"] = coordinates.latitude;
    if (coordinates.longitude) next["venue-create-longitude"] = coordinates.longitude;
    const reasonError = textError(draft.reason, { label: "o motivo", min: 3, max: 500 });
    if (reasonError) next["venue-create-reason"] = reasonError;
    if (Object.keys(next).length > 0) {
      setErrors(next);
      const first = [
        "venue-create-name",
        "venue-create-city",
        "venue-create-state",
        "venue-create-address",
        "venue-create-postal-code",
        "venue-create-latitude",
        "venue-create-longitude",
        "venue-create-reason",
      ].find((id) => next[id]);
      if (first) document.getElementById(first)?.focus();
      return;
    }
    setErrors({});
    createMutation.mutate({
      name: normalizeWhitespace(draft.name),
      city: normalizeWhitespace(draft.city),
      state: draft.state.trim().toUpperCase(),
      address_line: normalizeWhitespace(draft.address_line),
      postal_code: postalCode || null,
      latitude: coordinateValue(draft.latitude),
      longitude: coordinateValue(draft.longitude),
      is_public: draft.is_public,
      reason: draft.reason.trim(),
    });
  }

  return (
    <Modal
      open={open}
      title="Nova quadra"
      description="A quadra é criada na organização da plataforma e fica inativa até você adicionar espaços e publicar."
      onClose={close}
      closeOnOverlay={!createMutation.isPending}
      size="lg"
      footer={
        <>
          <button
            type="button"
            className="button button--ghost"
            onClick={close}
            disabled={createMutation.isPending}
          >
            Cancelar
          </button>
          <button
            type="submit"
            form="admin-venue-create-form"
            className="button button--primary"
            disabled={createMutation.isPending}
            aria-busy={createMutation.isPending || undefined}
          >
            {createMutation.isPending ? "Criando..." : "Criar quadra"}
          </button>
        </>
      }
    >
      <form id="admin-venue-create-form" className="form" onSubmit={submit} noValidate>
        {createMutation.error ? (
          <ErrorNotice
            message={createErrorMessage(createMutation.error)}
            requestId={requestIdOf(createMutation.error)}
          />
        ) : null}
        <TextField
          id="venue-create-name"
          label="Nome da quadra"
          value={draft.name}
          onChange={(event) => update({ name: event.target.value })}
          error={errors["venue-create-name"]}
          hint="Ex.: Arena Pública Centro."
          maxLength={120}
          required
          data-autofocus
        />
        <div className="form-row form-row--three">
          <TextField
            id="venue-create-city"
            label="Cidade"
            value={draft.city}
            onChange={(event) => update({ city: event.target.value })}
            error={errors["venue-create-city"]}
            maxLength={120}
            required
          />
          <TextField
            id="venue-create-state"
            label="UF"
            value={draft.state}
            onChange={(event) => update({ state: event.target.value.toUpperCase() })}
            error={errors["venue-create-state"]}
            maxLength={2}
            required
          />
          <TextField
            id="venue-create-postal-code"
            label="CEP"
            value={formatCep(draft.postal_code)}
            onChange={(event) => update({ postal_code: normalizeCep(event.target.value) })}
            error={errors["venue-create-postal-code"]}
            inputMode="numeric"
            maxLength={9}
          />
        </div>
        <div className="form-actions">
          <button
            type="button"
            className="button button--small button--ghost"
            onClick={lookupCep}
            disabled={lookupMutation.isPending}
            aria-busy={lookupMutation.isPending || undefined}
          >
            <SearchIcon size={16} />
            {lookupMutation.isPending ? "Buscando..." : "Buscar CEP"}
          </button>
          <span className="field__hint">
            Preenche cidade, UF, endereço e coordenadas a partir do CEP.
          </span>
        </div>
        {lookupMutation.error ? (
          <ErrorNotice
            message={adminErrorMessage(lookupMutation.error)}
            requestId={requestIdOf(lookupMutation.error)}
          />
        ) : null}
        {cepMessage ? <p className="field__hint">{cepMessage}</p> : null}
        <TextField
          id="venue-create-address"
          label="Endereço"
          value={draft.address_line}
          onChange={(event) => update({ address_line: event.target.value })}
          error={errors["venue-create-address"]}
          maxLength={200}
          required
        />
        <div className="form-row">
          <TextField
            id="venue-create-latitude"
            label="Latitude"
            value={draft.latitude}
            onChange={(event) => update({ latitude: event.target.value })}
            error={errors["venue-create-latitude"]}
            hint="Entre -90 e 90."
            inputMode="decimal"
            required
          />
          <TextField
            id="venue-create-longitude"
            label="Longitude"
            value={draft.longitude}
            onChange={(event) => update({ longitude: event.target.value })}
            error={errors["venue-create-longitude"]}
            hint="Entre -180 e 180."
            inputMode="decimal"
            required
          />
        </div>
        <CheckboxField
          id="venue-create-public"
          label="Aparece na descoberta do aplicativo"
          checked={draft.is_public}
          onChange={(checked) => update({ is_public: checked })}
          hint="A quadra só aparece depois de publicada e com ao menos um espaço ativo."
        />
        <TextField
          id="venue-create-reason"
          label="Motivo"
          value={draft.reason}
          onChange={(event) => update({ reason: event.target.value })}
          error={errors["venue-create-reason"]}
          hint="Obrigatório. Fica registrado na auditoria."
          maxLength={500}
          required
        />
      </form>
    </Modal>
  );
}
