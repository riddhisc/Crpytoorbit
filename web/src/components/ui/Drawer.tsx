import * as Dialog from "@radix-ui/react-dialog";

export function Modal({
  open,
  onOpenChange,
  title,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50" />
        <Dialog.Content className="fixed left-1/2 top-1/2 w-[min(520px,calc(100%-32px))] -translate-x-1/2 -translate-y-1/2 rounded-lg border border-line bg-surface p-5 shadow-soft">
          <Dialog.Title className="text-lg">{title}</Dialog.Title>
          <div className="mt-3">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function Drawer({
  open,
  onOpenChange,
  title,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40" />
        <Dialog.Content className="fixed inset-y-0 right-0 flex w-full max-w-xl flex-col overflow-auto border-l border-line bg-surface p-5 shadow-soft sm:max-w-xl">
          <Dialog.Title className="text-lg">{title}</Dialog.Title>
          <Dialog.Description className="sr-only">Exception evidence and resolution</Dialog.Description>
          <div className="mt-4 flex-1">{children}</div>
          <Dialog.Close className="mt-4 min-h-11 self-start rounded-md border border-line px-3">Close</Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
