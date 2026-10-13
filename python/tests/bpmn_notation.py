"""One BPMN 2.0 document holding the notation the canvas draws beyond plain
process flow: multiple triggers, a non-interrupting start, a message on a flow,
conversations and a choreography. Kept inline rather than in fixtures/, which
the architecture input contract walks."""

NS = "http://example.org/bpmn-notation#"

NOTATION_TTL = """
@prefix bpmn: <https://sBPMN.github.io/2.0/classes#> .
@prefix bp:   <https://sBPMN.github.io/2.0/properties#> .
@prefix ex:   <http://example.org/bpmn-notation#> .

ex:Collab a bpmn:collaboration ; bp:name "Order handling" ;
    bp:participant ex:Shop, ex:Customer, ex:Bank ;
    bp:messageFlow ex:Ask ;
    bp:conversationNode ex:Talk, ex:Pay, ex:Ship ;
    bp:conversationLink ex:TalkToShop .

ex:Shop a bpmn:participant ; bp:name "Shop" ; bp:processRef ex:ShopProcess .
ex:Customer a bpmn:participant ; bp:name "Customer" .
ex:Bank a bpmn:participant ; bp:name "Bank" .

ex:ShopProcess a bpmn:process ; bp:name "Shop process" ;
    bp:contains ex:Arrives, ex:Handle, ex:Both, ex:Done, ex:Watch,
        ex:F1, ex:F2, ex:F3 .

ex:Arrives a bpmn:startEvent ; bp:name "Order arrives" ;
    bp:eventDefinition ex:ArrivesByMessage, ex:ArrivesBySignal .
ex:ArrivesByMessage a bpmn:messageEventDefinition .
ex:ArrivesBySignal a bpmn:signalEventDefinition .

ex:Handle a bpmn:task ; bp:name "Handle order" .

ex:Both a bpmn:intermediateCatchEvent ; bp:name "Paid and packed" ;
    bp:parallelMultiple true ;
    bp:eventDefinition ex:BothMessage, ex:BothCondition .
ex:BothMessage a bpmn:messageEventDefinition .
ex:BothCondition a bpmn:conditionalEventDefinition .

ex:Done a bpmn:endEvent ; bp:name "Confirmed" ;
    bp:eventDefinition ex:DoneMessage, ex:DoneSignal .
ex:DoneMessage a bpmn:messageEventDefinition .
ex:DoneSignal a bpmn:signalEventDefinition .

ex:Watch a bpmn:subProcess ; bp:name "Watch for a change" ;
    bp:triggeredByEvent true ; bp:contains ex:Changed .
ex:Changed a bpmn:startEvent ; bp:name "Order changed" ;
    bp:isInterrupting false ; bp:eventDefinition ex:ChangedByMessage .
ex:ChangedByMessage a bpmn:messageEventDefinition .

ex:F1 a bpmn:sequenceFlow ; bp:sourceRef ex:Arrives ; bp:targetRef ex:Handle .
ex:F2 a bpmn:sequenceFlow ; bp:sourceRef ex:Handle ; bp:targetRef ex:Both .
ex:F3 a bpmn:sequenceFlow ; bp:sourceRef ex:Both ; bp:targetRef ex:Done .

ex:Ask a bpmn:messageFlow ; bp:name "orders" ;
    bp:sourceRef ex:Customer ; bp:targetRef ex:Arrives ; bp:messageRef ex:OrderMessage .
ex:OrderMessage a bpmn:message ; bp:name "Order" .

ex:Talk a bpmn:conversation ; bp:name "Ordering" ;
    bp:participantRef ex:Shop, ex:Customer .
ex:TalkToShop a bpmn:conversationLink ; bp:sourceRef ex:Shop ; bp:targetRef ex:Talk .
ex:Pay a bpmn:subConversation ; bp:name "Payment" ;
    bp:participantRef ex:Shop, ex:Bank .
ex:Ship a bpmn:callConversation ; bp:name "Shipping" ;
    bp:participantRef ex:Shop .

ex:Delivery a bpmn:choreography ; bp:name "Delivery" ;
    bp:participant ex:Courier, ex:Recipient ;
    bp:flowElement ex:Begin, ex:Quote, ex:Settle, ex:Agree, ex:End,
        ex:C1, ex:C2, ex:C3, ex:C4 .
ex:Courier a bpmn:participant ; bp:name "Courier" ;
    bp:participantMultiplicity ex:ManyCouriers .
ex:ManyCouriers a bpmn:participantMultiplicity .
ex:Recipient a bpmn:participant ; bp:name "Recipient" .

ex:Begin a bpmn:startEvent ; bp:name "Parcel ready" .
ex:Quote a bpmn:choreographyTask ; bp:name "Request a quote" ;
    bp:participantRef ex:Courier, ex:Recipient ;
    bp:initiatingParticipantRef ex:Recipient ;
    bp:messageFlowRef ex:QuoteAsked, ex:QuoteGiven ;
    bp:loopType "Standard" .
ex:QuoteAsked a bpmn:messageFlow ;
    bp:sourceRef ex:Recipient ; bp:targetRef ex:Courier ; bp:messageRef ex:QuoteRequest .
ex:QuoteGiven a bpmn:messageFlow ;
    bp:sourceRef ex:Courier ; bp:targetRef ex:Recipient ; bp:messageRef ex:QuoteOffer .
ex:QuoteRequest a bpmn:message ; bp:name "Quote request" .
ex:QuoteOffer a bpmn:message ; bp:name "Quote" .
ex:Settle a bpmn:subChoreography ; bp:name "Settle payment" ;
    bp:participantRef ex:Courier, ex:Recipient ;
    bp:initiatingParticipantRef ex:Recipient ;
    bp:loopType "MultiInstanceParallel" .
ex:Agree a bpmn:callChoreography ; bp:name "Agree terms" ;
    bp:participantRef ex:Courier, ex:Recipient ;
    bp:initiatingParticipantRef ex:Courier .
ex:End a bpmn:endEvent ; bp:name "Delivered" .

ex:C1 a bpmn:sequenceFlow ; bp:sourceRef ex:Begin ; bp:targetRef ex:Quote .
ex:C2 a bpmn:sequenceFlow ; bp:sourceRef ex:Quote ; bp:targetRef ex:Settle .
ex:C3 a bpmn:sequenceFlow ; bp:sourceRef ex:Settle ; bp:targetRef ex:Agree .
ex:C4 a bpmn:sequenceFlow ; bp:sourceRef ex:Agree ; bp:targetRef ex:End .
"""
