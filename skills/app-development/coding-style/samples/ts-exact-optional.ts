// exactOptionalPropertyTypes companion: conditional spread to rebuild optional fields
// From model-jetty/packages/core/src/contracts/request-schemas.ts:35-56 (read 2026-10-05)
//
// In repos with exactOptionalPropertyTypes on, optional fields are precisely rebuilt with conditional spreads
// when reconstructing a DTO from unknown - never passed straight through, so no ghost undefined property enters the type layer.
// Original in-file comment: "Exact optional properties are reconstructed, never asserted
// from unknown input."

    const serialized = JSON.stringify(input);
    if (serialized.length > maxBytes || new TextEncoder().encode(serialized).byteLength > maxBytes) throw new Error('limit');
    const parsed = modelRequestSchema.safeParse(input);
    if (!parsed.success) throw new Error('schema');
    // Exact optional properties are reconstructed, never asserted from unknown input.
    return {
      model: parsed.data.model,
      messages: parsed.data.messages.map((message): ModelRequest['messages'][number] => {
        if (message.role === 'assistant') return { role: message.role, text: message.text, ...(message.toolCalls === undefined ? {} : { toolCalls: message.toolCalls }) };
        if (message.role === 'user') return { role: message.role, text: message.text, ...(message.images === undefined ? {} : { images: message.images.map((image) => ({ mediaType: image.mediaType, dataBase64: image.dataBase64 })) }) };
        return message;
      }),
      ...(parsed.data.tools === undefined ? {} : { tools: parsed.data.tools.map((tool) => ({ name: tool.name, parameters: tool.parameters, ...(tool.description === undefined ? {} : { description: tool.description }) })) }),
      ...(parsed.data.instructions === undefined ? {} : { instructions: parsed.data.instructions }),
      ...(parsed.data.reasoningEffort === undefined ? {} : { reasoningEffort: parsed.data.reasoningEffort }),
      ...(parsed.data.speed === undefined ? {} : { speed: parsed.data.speed }),
      ...(parsed.data.conversationId === undefined ? {} : { conversationId: parsed.data.conversationId }),
    };
  } catch { throw new Error('Invalid model request'); }

// ❌ Counterexample (constructed, not repository code): spreading optional fields from an unknown source in one go
// return { ...parsed.data };  // ghost undefined properties enter the type layer; downstream cannot tell "absent" from "present as undefined"
