import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/layout/AppShell";
import { AssistantPanel } from "@/components/common/AssistantPanel";

export const Route = createFileRoute("/assistant")({
  head: () => ({
    meta: [
      { title: "ProctorAI Guide · Assistant" },
      {
        name: "description",
        content:
          "Rule-based ProctorAI Guide for setup and review help. Does not answer exam questions.",
      },
    ],
  }),
  component: AssistantPage,
});

function AssistantPage() {
  return (
    <AppShell>
      <div className="mx-auto h-[75vh] max-w-3xl">
        <AssistantPanel embedded />
      </div>
    </AppShell>
  );
}
