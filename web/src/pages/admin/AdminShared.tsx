import { EmptyState } from "../../components/Feedback";
import { ShieldIcon } from "../../components/ui/Icons";

export function AdminForbiddenState() {
  return (
    <EmptyState title="Acesso restrito" icon={<ShieldIcon size={30} />}>
      Sua conta não tem permissão de administração da plataforma.
    </EmptyState>
  );
}
